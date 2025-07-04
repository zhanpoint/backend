import json
import logging

from django.db import transaction
from rest_framework import permissions, status, viewsets
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response

from dream.serializers.dream_serializers import (
    DreamCreateSerializer,
    DreamSerializer,
)
from dream.tasks.image_tasks import delete_images, upload_images

from ..models import Dream, DreamCategory, DreamImage, Tag

logger = logging.getLogger(__name__)


class DreamViewSet(viewsets.ModelViewSet):
    """
    一个用于处理梦境（Dream）资源的视图集。

    提供了对梦境记录的 CRUD（创建、读取、更新、删除）操作，并集成了
    复杂的业务逻辑，如图片处理、标签管理和分类。
    """

    # === ViewSet Configuration ===

    # 权限和解析器配置
    # 确保只有已认证的用户才能访问，并支持多种数据格式的请求
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]

    # === Core ViewSet Methods ===

    def get_queryset(self):
        """
        获取当前认证用户的梦境记录。

        为了优化性能，此方法使用了 select_related 和 prefetch_related
        来减少数据库查询次数。
        """
        user = self.request.user
        return (
            Dream.objects.filter(user=user)
            .select_related("user")
            .prefetch_related(
                "categories", "theme_tags", "character_tags", "location_tags", "images"
            )
            .order_by("-created_at")
        )

    def get_serializer_class(self):
        """根据请求操作（Action）动态选择合适的序列化器。"""
        if self.action in ["create", "update", "partial_update"]:
            return DreamCreateSerializer
        return DreamSerializer

    # === Action Methods ===

    def list(self, request, *args, **kwargs):
        """处理获取梦境列表的请求，并在内容中插入图片。"""
        queryset = self.get_queryset()
        for dream in queryset:
            dream.content = self._insert_images_to_content(dream)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """处理获取单个梦境详情的请求，并在内容中插入图片。"""
        instance = self.get_object()
        instance.content = self._insert_images_to_content(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """
        处理创建新梦境的请求。

        此操作是原子的，确保数据一致性。图片上传将作为后台任务处理。
        """
        try:
            form_data = self._extract_form_data(request)

            dream = Dream.objects.create(
                title=form_data["title"],
                content=form_data["content"],
                user=request.user,
            )

            # 处理关联的分类和标签
            self._process_categories(dream, form_data.get("categories", []))
            tags_data = form_data.get("tags", {})
            for tag_type in ["theme", "character", "location"]:
                tags = tags_data.get(tag_type, [])
                if tags:
                    self._process_tags(dream, tags, tag_type)

            # 仅当数据库事务成功提交后，才启动图片上传的后台任务
            transaction.on_commit(
                lambda: self._process_image_uploads(dream, request)
            )

            # 准备并返回响应数据
            dream.content = self._insert_images_to_content(dream)
            serializer = DreamSerializer(dream)
            response_data = serializer.data

            # 如果有新图片上传，添加WebSocket通知信息
            if request.FILES:
                response_data["images_status"] = {
                    "status": "processing",
                    "websocket_url": f"/ws/dream-images/{dream.id}/",
                    "images": [],
                }

            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建梦境记录失败: {e}")
            return Response(
                {"detail": f"创建梦境记录失败: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """
        处理更新现有梦境的请求。

        此操作是原子的。它会处理基本信息、分类、标签和图片的变更。
        """
        try:
            instance = self.get_object()
            form_data = self._extract_form_data(request)

            # 更新基本信息
            instance.title = form_data.get("title", instance.title)
            instance.content = form_data.get("content", instance.content)
            instance.save()

            # 更新分类
            instance.categories.clear()
            self._process_categories(instance, form_data.get("categories", []))

            # 更新标签
            tags_data = form_data.get("tags", {})
            for tag_type in ["theme", "character", "location"]:
                current_tags = list(getattr(instance, f"{tag_type}_tags").all())
                getattr(instance, f"{tag_type}_tags").clear()
                self._process_tags(instance, tags_data.get(tag_type, []), tag_type)
                self._cleanup_unused_tags(current_tags)

            # 处理图片（删除旧图片，添加新图片）
            self._process_image_changes(instance, form_data, request)

            # 准备并返回响应数据
            instance.content = self._insert_images_to_content(instance)
            serializer = DreamSerializer(instance)
            response_data = serializer.data

            # 如果有新图片上传，添加WebSocket通知信息
            if request.FILES:
                response_data["images_status"] = {
                    "status": "processing",
                    "websocket_url": f"/ws/dream-images/{instance.id}/",
                    "message": "正在处理新上传的图片，稍后将自动更新",
                    "images": [],
                }

            return Response(response_data)

        except Exception as e:
            logger.error(f"更新梦境记录失败: {e}")
            return Response(
                {"detail": f"更新梦境记录失败: {e}"},
                status=status.HTTP_400_BAD_REQUEST,
            )

    def destroy(self, request, *args, **kwargs):
        """
        处理删除梦境的请求。

        在删除梦境记录前，会先启动一个后台任务来删除关联的云存储（OSS）图片。
        """
        try:
            instance = self.get_object()
            image_queryset = DreamImage.objects.filter(dream=instance)
            
            if image_queryset.exists():
                image_details = [
                    {"id": image.id, "url": image.image_url} for image in image_queryset
                ]
                delete_images(instance.id, image_details, request.user.username)
                logger.info(f"已将{len(image_details)}个图片发送到删除队列")

            return super().destroy(request, *args, **kwargs)

        except Exception as e:
            logger.error(f"删除梦境记录失败: {e}")
            return Response(
                {"error": f"删除梦境记录失败: {e}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

    # === Private Methods ===

    # --- Data Handling ---

    def _extract_form_data(self, request):
        """从请求中安全地提取并解析表单数据。"""
        form_data = {}
        text_fields = ["title", "content"]
        json_fields = ["categories", "tags", "remoteImages"]

        for field in text_fields:
            form_data[field] = request.data.get(field, "")

        for field in json_fields:
            json_string = request.data.get(field)
            if json_string:
                try:
                    form_data[field] = (
                        json.loads(json_string)
                        if isinstance(json_string, str)
                        else json_string
                    )
                except json.JSONDecodeError:
                    logger.error(f"解析JSON字段 '{field}' 失败: {json_string}")
                    form_data[field] = [] if field != "tags" else {}
        return form_data

    def _insert_images_to_content(self, dream):
        """将梦境关联的图片URL按位置插入到其内容中，生成最终的Markdown文本。"""
        content = dream.content
        offset = 0
        # 按位置升序排列图片
        for image_obj in dream.images.all().order_by("position"):
            position = image_obj.position + offset
            markdown_image = f"![图片]({image_obj.image_url})"
            content = content[:position] + markdown_image + content[position:]
            offset += len(markdown_image)
        return content

    # --- Category & Tag Processing ---

    def _process_categories(self, dream, category_names):
        """处理并关联梦境的分类。"""
        for name in category_names:
            try:
                category = DreamCategory.objects.get(name=name)
                dream.categories.add(category)
            except DreamCategory.DoesNotExist:
                raise ValidationError(f"分类 '{name}' 不存在")

    def _process_tags(self, dream, tag_names, tag_type):
        """处理并关联梦境的标签（主题、角色、地点）。"""
        tag_field_map = {
            "theme": dream.theme_tags,
            "character": dream.character_tags,
            "location": dream.location_tags,
        }
        for name in tag_names:
            tag, _ = Tag.objects.get_or_create(name=name, tag_type=tag_type)
            tag_field_map[tag_type].add(tag)

    def _cleanup_unused_tags(self, tags_to_check):
        """
        清理不再被任何梦境引用的标签，以保持数据整洁。

        Args:
            tags_to_check (list[Tag]): 一个包含待检查标签对象的列表。
        """
        related_field_map = {
            "theme": "dream_themes",
            "character": "dream_characters",
            "location": "dream_locations",
        }
        for tag in tags_to_check:
            related_field_name = related_field_map.get(tag.tag_type)
            if related_field_name and getattr(tag, related_field_name).count() == 0:
                logger.info(f"删除未使用的标签: {tag.name} (类型: {tag.tag_type})")
                tag.delete()

    # --- Image Processing ---

    def _process_image_changes(self, dream, form_data, request):
        """
        处理梦境更新时的图片变更。

        - 删除处理：识别并删除不再使用的图片记录，并异步删除云存储文件。
        - 上传处理：触发新上传图片的异步处理任务。
        """
        try:
            # 1. 删除不再使用的图片
            new_image_urls = {img["url"] for img in form_data.get("remoteImages", [])}
            
            images_to_delete = dream.images.exclude(image_url__in=new_image_urls)
            
            if images_to_delete.exists():
                image_details = [
                    {"id": image.id, "url": image.image_url}
                    for image in images_to_delete
                ]
                
                # 异步删除云存储（OSS）中的文件
                transaction.on_commit(
                    lambda: delete_images(dream.id, image_details, request.user.username)
                )

                # 立即从数据库中删除记录
                count, _ = images_to_delete.delete()
                logger.info(f"已删除 {count} 条不再使用的图片数据库记录")

            # 2. 异步处理新上传的图片
            if request.FILES:
                transaction.on_commit(
                    lambda: self._process_image_uploads(dream, request)
                )

        except Exception as e:
            logger.error(f"处理图片变更失败: {e}")
            raise ValidationError(f"处理图片变更失败: {e}")

    def _process_image_uploads(self, dream, request):
        """
        准备并触发一个后台任务来处理新上传的图片。
        """
        try:
            image_files, positions = [], []
            
            # 从请求中收集图片文件和元数据
            for key in request.FILES:
                if key.startswith("imageFile_"):
                    index = key.split("_")[1]
                    file = request.FILES[key]
                    
                    # 解析元数据以获取图片位置
                    metadata_str = request.data.get(f"imageMetadata_{index}", "{}")
                    metadata = json.loads(metadata_str) if isinstance(metadata_str, str) else metadata_str
                    
                    image_files.append({"name": file.name, "data": file.read()})
                    positions.append(metadata.get("position", 0))

            # 如果有图片，则发送到后台任务队列
            if image_files:
                upload_images(dream.id, image_files, positions)
                logger.info(f"已将 {len(image_files)} 个新图片发送到处理队列")

        except Exception as e:
            logger.error(f"图片上传任务准备失败: {e}")
            raise ValidationError(f"图片上传任务准备失败: {e}")
