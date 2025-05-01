from rest_framework import viewsets, permissions, status
from rest_framework.response import Response
from rest_framework.exceptions import ValidationError
from rest_framework.parsers import MultiPartParser, FormParser, JSONParser
from django.db import transaction
import json
import logging

# 创建日志记录器实例
logger = logging.getLogger(__name__)

from ..models import Dream, DreamCategory, Tag, DreamImage
from dream.serializers.dream_serializers import (
    DreamSerializer,
    DreamCreateSerializer,
)
from dream.celery.tasks.image_tasks import upload_images, delete_images


class DreamViewSet(viewsets.ModelViewSet):
    # 认证之后的第二道防线：权限检查：确保只有已认证的用户才能访问该视图/接口，未登录用户访问会返回 401 Unauthorized 响应
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]  # 支持多种解析器

    # 获取当前登录用户的梦境记录
    def get_queryset(self):
        user = self.request.user
        return Dream.objects.filter(user=user).select_related('user').prefetch_related(
            'categories', 'theme_tags', 'character_tags',
            'location_tags', 'images'
        ).order_by('-created_at')

    # 选择合适的序列化器
    def get_serializer_class(self):
        """根据请求方法选择合适的序列化器"""
        if self.action in ['create', 'update', 'partial_update']:
            return DreamCreateSerializer
        return DreamSerializer

    # 处理列表请求
    def list(self, request, *args, **kwargs):
        queryset = self.get_queryset()
        for dream in queryset:
            dream.content = self._insert_images_to_content(dream)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    # 处理详情请求
    def retrieve(self, request, *args, **kwargs):
        instance = self.get_object()
        instance.content = self._insert_images_to_content(instance)
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    def _insert_images_to_content(self, dream):
        """将图片插入到内容中显示"""
        content = dream.content
        offset = 0
        for image_obj in dream.images.all().order_by('position'):
            position, dream_url = image_obj.position + offset, image_obj.image_url
            markdown_image = f"![图片]({dream_url})"
            content = content[:position] + markdown_image + content[position:]
            offset += len(markdown_image)
        return content

    # 处理创建请求
    @transaction.atomic
    def create(self, request, *args, **kwargs):
        try:
            # 从请求中提取表单数据
            form_data = self._extract_form_data(request)

            # 创建梦境记录
            dream = Dream.objects.create(
                title=form_data['title'],
                content=form_data['content'],
                user=request.user
            )

            # 处理分类
            self._process_categories(dream, form_data.get('categories', []))

            # 处理标签
            tags_data = form_data.get('tags', {})
            for tag_type in ['theme', 'character', 'location']:
                tags = tags_data.get(tag_type, [])
                if tags:
                    self._process_tags(dream, tags, tag_type)

            # 处理图片上传
            self._process_image_uploads(dream, request)

            # 序列化并返回完整的梦境数据
            dream.content = self._insert_images_to_content(dream)
            
            # 获取序列化数据并添加额外信息
            serializer = DreamSerializer(dream)
            response_data = serializer.data
            
            # 如果有等待处理的图片，添加WebSocket连接信息
            has_images = request.FILES and any(key.startswith('imageFile_') for key in request.FILES.keys())
            if has_images:
                response_data['images_status'] = {
                    'status': 'processing',
                    'websocket_url': f'/ws/dream-images/{dream.id}/',
                    'images': []  # 预留空图片列表，将通过WebSocket更新
                }
            
            return Response(response_data, status=status.HTTP_201_CREATED)

        except Exception as e:
            logger.error(f"创建梦境记录失败: {str(e)}")
            return Response({"detail": f"创建梦境记录失败: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST)

    # 处理更新请求
    @transaction.atomic
    def update(self, request, *args, **kwargs):
        try:
            # 获取当前梦境记录
            instance = self.get_object()

            # 从请求中提取表单数据
            form_data = self._extract_form_data(request)

            # 更新基本信息
            instance.title = form_data.get('title', instance.title)
            instance.content = form_data.get('content', instance.content)
            instance.save()

            # 处理分类
            instance.categories.clear()
            self._process_categories(instance, form_data['categories'])

            # 处理标签
            tags_data = form_data.get('tags', {})
            for tag_type in ['theme', 'character', 'location']:
                # 获取当前梦境的所有标签记录
                current = list(getattr(instance, f'{tag_type}_tags').all())
                # 删除dream——tag中间表记录
                getattr(instance, f'{tag_type}_tags').clear()
                # 添加标签
                self._process_tags(instance, tags_data[tag_type], tag_type)
                # 删除不再使用的标签
                self._cleanup_unused_tags(current, tag_type)

            # 处理图片操作
            # 1. 检查需要删除的图片
            self._process_image_changes(instance, form_data, request)

            # 序列化并返回完整的梦境数据
            instance.content = self._insert_images_to_content(instance)
            serializer = DreamSerializer(instance)
            
            # 获取序列化数据并添加额外信息
            response_data = serializer.data
            
            # 检查是否有新图片上传
            has_new_images = request.FILES and any(key.startswith('imageFile_') for key in request.FILES.keys())
            
            # 如果有新图片，添加WebSocket连接信息
            if has_new_images:
                response_data['images_status'] = {
                    'status': 'processing',
                    'websocket_url': f'/ws/dream-images/{instance.id}/',
                    'message': '正在处理新上传的图片，稍后将自动更新',
                    'images': []  # 预留空图片列表，将通过WebSocket更新
                }
            
            return Response(response_data)

        except Exception as e:
            logger.error(f"更新梦境记录失败: {str(e)}")
            return Response({"detail": f"更新梦境记录失败: {str(e)}"},
                            status=status.HTTP_400_BAD_REQUEST)

    def _process_image_changes(self, dream, form_data, request):
        """
        处理梦境图片变更，包括删除不再使用的图片和添加新图片
        - 对比现有图片和表单中的图片
        - 异步删除不再使用的图片
        - 异步处理新上传的图片
        
        Args:
            dream: 梦境实例
            form_data: 处理过的表单数据
            request: 请求对象
        """
        try:
            # 1. 查找需要删除的图片
            image_new_urls = [obj['url'] for obj in form_data.get('remoteImages', [])]
            image_old_urls = list(DreamImage.objects.filter(dream=dream).values_list('image_url', flat=True))
            
            # 计算需要删除的图片URL
            delete_image_urls = list(set(image_old_urls) - set(image_new_urls))
            
            # 2. 异步删除不再使用的图片
            if delete_image_urls:
                self._async_delete_images(dream.id, delete_image_urls, request.user.username)
                
            # 3. 异步处理新上传的图片
            if request.FILES:
                self._process_image_uploads(dream, request)
                
        except Exception as e:
            logger.error(f"处理图片变更失败: {str(e)}")
            raise ValidationError(f"处理图片变更失败: {str(e)}")
    
    def _async_delete_images(self, dream_id, delete_image_urls, username):
        """
        异步删除图片
        - 获取图片详细信息
        - 发送到Celery任务队列进行异步删除
        
        Args:
            dream_id: 梦境ID
            delete_image_urls: 需要删除的图片URL列表
            username: 用户名，用于OSS操作
        """
        try:
            # 获取图片详细信息
            image_details = []
            for url in delete_image_urls:
                # 查找图片记录
                image = DreamImage.objects.filter(image_url=url).first()
                if image:
                    image_details.append({
                        'id': image.id,
                        'url': url
                    })
                    # 立即删除数据库记录（图片实体由Celery异步删除）
                    image.delete()
                else:
                    logger.warning(f"找不到图片记录: {url}")
            
            # 如果有图片需要删除，发送到Celery任务队列
            if image_details:
                delete_images(dream_id, image_details, username)
                logger.info(f"已将{len(image_details)}个图片发送到删除队列")
                
        except Exception as e:
            logger.error(f"发起异步删除图片失败: {str(e)}")
            # 不抛出异常，避免影响整个更新流程
            # 这里图片删除失败不应该导致整个梦境更新失败

    def _extract_form_data(self, request):
        """从请求中提取表单数据"""
        form_data = {}

        # 文本字段处理
        form_data['title'] = request.data.get('title', '')
        form_data['content'] = request.data.get('content', '')

        # JSON字段处理
        json_fields = ['categories', 'tags', 'remoteImages', 'imageMetadata']
        for field in json_fields:
            json_field = request.data.get(field)
            if json_field:
                try:
                    if isinstance(json_field, str):
                        form_data[field] = json.loads(json_field)
                    else:
                        form_data[field] = json_field
                except json.JSONDecodeError:
                    logger.error(f"解析{field}字段失败: {json_field}")
                    form_data[field] = {} if field == 'imageOperations' else []

        return form_data

    # 处理分类
    def _process_categories(self, dream, categories):
        """处理梦境分类"""
        for category_name in categories:
            try:
                category = DreamCategory.objects.get(name=category_name)
                dream.categories.add(category)
            except DreamCategory.DoesNotExist:
                raise ValidationError(f"分类 '{category_name}' 不存在")

    # 处理标签
    def _process_tags(self, dream, tag_list, tag_type):
        """处理标签"""
        tag_field_map = {
            'theme': dream.theme_tags,
            'character': dream.character_tags,
            'location': dream.location_tags
        }
        for tag_name in tag_list:
            # 获取或创建标签
            tag, created = Tag.objects.get_or_create(
                name=tag_name,
                tag_type=tag_type,
            )
            # 添加相应的关系到Dream—Tag中间表
            tag_field_map[tag_type].add(tag)

    # 清理不再被任何梦境引用的标签
    def _cleanup_unused_tags(self, tags, type):
        # 检查标签类型对应的关系字段
        related_field_map = {
            'theme': 'dream_themes',
            'character': 'dream_characters',
            'location': 'dream_locations'
        }
        for tag in tags:
            related_field = related_field_map.get(type)
            if related_field:
                # 获取关联的梦境数量
                related_dreams_count = getattr(tag, related_field).count()

                # 如果没有关联的梦境，则删除标签
                if related_dreams_count == 0:
                    logger.info(f"删除未使用的标签: {tag.name} (类型: {tag.tag_type})")
                    tag.delete()

    def _process_image_uploads(self, dream, request):
        """
        处理图片上传
        - 收集图片信息
        - 通过Celery任务队列异步处理图片
        """
        try:
            image_files = []
            positions = []
            
            # 收集图片文件和元数据
            for index, file_key in [(key.split('_')[1], value) for key, value in request.FILES.items() 
                                  if key.startswith('imageFile_')]:
                try:
                    # 获取位置信息
                    metadata_key = f'imageMetadata_{index}'
                    position = 0
                    
                    if metadata_key in request.data:
                        metadata = request.data.get(metadata_key)
                        if metadata:
                            if isinstance(metadata, str):
                                metadata = json.loads(metadata)
                            position = metadata.get('position', 0)
                    
                    # 读取文件数据
                    file_data = file_key.read()
                    
                    # 添加到待处理列表
                    image_files.append({
                        'name': file_key.name,
                        'data': file_data
                    })
                    positions.append(position)
                    
                except Exception as e:
                    logger.error(f"处理图片文件失败: {str(e)}")
                    raise ValidationError(f"处理图片文件失败: {str(e)}")
            
            # 如果有图片需要处理，发送到Celery任务队列
            if image_files:
                upload_images(dream.id, image_files, positions)
                logger.info(f"已将{len(image_files)}个图片发送到处理队列")
                
        except Exception as e:
            logger.error(f"图片上传失败: {str(e)}")
            raise ValidationError(f"图片上传失败: {str(e)}")

    def destroy(self, request, *args, **kwargs):
        """
        删除梦境记录，同时异步删除关联的OSS图片
        """
        try:
            # 获取梦境记录
            instance = self.get_object()
            
            # 获取梦境ID和用户名
            dream_id = instance.id
            username = request.user.username
            
            # 获取所有关联的图片URL
            dream_images = DreamImage.objects.filter(dream=instance)
            image_urls = []
            
            for image in dream_images:
                image_urls.append({
                    'id': image.id,
                    'url': image.image_url
                })
            
            # 如果有图片需要删除，先发送异步删除任务
            if image_urls:
                # 关键修复：先发送异步删除任务，再删除梦境记录
                task_id = delete_images(dream_id, image_urls, username)
                logger.info(f"已将{len(image_urls)}个图片发送到删除队列, 任务ID: {task_id}")
            
            # 最后删除梦境记录
            response = super().destroy(request, *args, **kwargs)
            
            return response
            
        except Exception as e:
            logger.error(f"删除梦境记录失败: {str(e)}")
            return Response(
                {"error": f"删除梦境记录失败: {str(e)}"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
