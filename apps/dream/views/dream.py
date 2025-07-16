import json

from django.db import transaction
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.db import models
from rest_framework import permissions, status, viewsets, filters
from rest_framework.decorators import action
from rest_framework.parsers import FormParser, JSONParser, MultiPartParser
from rest_framework.response import Response
from django_filters.rest_framework import DjangoFilterBackend

from apps.dream.serializers.dream_serializers import (
    DreamCreateSerializer,
    DreamUpdateSerializer,
    DreamSerializer,
    DreamListSerializer,
    DreamJournalSerializer,
    SleepPatternSerializer,
    DreamCategorySerializer,
    TagSerializer,
)

from apps.dream.utils.image_manager import ImageLifecycleManager
from ..models import Dream, DreamCategory, DreamJournal, SleepPattern, Tag


class DreamViewSet(viewsets.ModelViewSet):
    """
    梦境记录的完整CRUD视图集 - 支持图片软删除管理
    """
    permission_classes = [permissions.IsAuthenticated]
    parser_classes = [MultiPartParser, FormParser, JSONParser]
    filter_backends = [DjangoFilterBackend, filters.SearchFilter, filters.OrderingFilter]
    filterset_fields = ['privacy', 'lucidity_level', 'is_favorite', 'is_recurring']
    search_fields = ['title', 'content', 'interpretation']
    ordering_fields = ['dream_date', 'created_at', 'lucidity_level']
    ordering = ['-dream_date', '-created_at']

    def get_queryset(self):
        """获取当前用户的梦境记录"""
        user = self.request.user
        queryset = Dream.objects.filter(user=user).select_related('user').prefetch_related(
            'categories', 'tags', 'images', 'related_dreams'
        )
        
        # 按分类过滤
        category = self.request.query_params.get('category')
        if category:
            queryset = queryset.filter(categories__name=category)
        
        # 按标签过滤
        tags = self.request.query_params.get('tags')
        if tags:
            tag_list = tags.split(',')
            queryset = queryset.filter(tags__name__in=tag_list).distinct()
        
        # 按日期范围过滤
        date_from = self.request.query_params.get('date_from')
        date_to = self.request.query_params.get('date_to')
        if date_from:
            queryset = queryset.filter(dream_date__gte=date_from)
        if date_to:
            queryset = queryset.filter(dream_date__lte=date_to)
        
        return queryset

    def get_serializer_class(self):
        """根据操作选择序列化器"""
        if self.action == 'list':
            return DreamListSerializer
        elif self.action in ['create']:
            return DreamCreateSerializer
        elif self.action in ['update', 'partial_update']:
            return DreamUpdateSerializer
        return DreamSerializer

    def list(self, request, *args, **kwargs):
        """获取梦境列表"""
        queryset = self.filter_queryset(self.get_queryset())
        
        # 分页
        page = self.paginate_queryset(queryset)
        if page is not None:
            for dream in page:
                dream.content = self._insert_images_to_content(dream)
            serializer = self.get_serializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        # 不分页的情况
        for dream in queryset:
            dream.content = self._insert_images_to_content(dream)
        serializer = self.get_serializer(queryset, many=True)
        return Response(serializer.data)

    def retrieve(self, request, *args, **kwargs):
        """获取单个梦境详情"""
        instance = self.get_object()
        serializer = self.get_serializer(instance)
        return Response(serializer.data)

    @transaction.atomic
    def create(self, request, *args, **kwargs):
        """创建新梦境 - 包含图片生命周期管理"""
        # 提取表单数据
        form_data = self._extract_form_data(request)
        
        # 设置用户
        form_data['user'] = request.user
        
        # 如果没有设置梦境日期，使用今天
        if not form_data.get('dream_date'):
            form_data['dream_date'] = timezone.now().date()
        
        # 创建序列化器实例
        serializer = self.get_serializer(data=form_data, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # 保存梦境
        dream = serializer.save(user=request.user)
        
        # 处理图片生命周期管理
        try:
            image_manager = ImageLifecycleManager(request.user)
            image_manager.process_dream_image_changes(
                dream=dream,
                old_content=None,  # 新创建，没有旧内容
                new_content=dream.content
            )
        except Exception as e:
            # 如果图片处理失败，记录错误但不影响梦境创建
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"梦境创建后图片处理失败: {e}")
        
        return Response(DreamSerializer(dream).data, status=status.HTTP_201_CREATED)

    @transaction.atomic
    def update(self, request, *args, **kwargs):
        """更新梦境 - 支持图片软删除"""
        instance = self.get_object()
        partial = kwargs.pop('partial', False)
        
        # 保存旧的内容用于图片差异比较
        old_content = instance.content
        
        # 提取表单数据
        form_data = self._extract_form_data(request)
        
        # 创建序列化器并验证
        serializer = self.get_serializer(instance, data=form_data, partial=partial, context={'request': request})
        serializer.is_valid(raise_exception=True)
        
        # 保存更新
        dream = serializer.save()
        
        # 处理图片生命周期管理
        try:
            image_manager = ImageLifecycleManager(request.user)
            image_manager.process_dream_image_changes(
                dream=dream,
                old_content=old_content,
                new_content=dream.content
            )
        except Exception as e:
            # 如果图片处理失败，记录错误但不影响梦境更新
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"梦境更新后图片处理失败: {e}")
        
        return Response(DreamSerializer(dream).data)

    def destroy(self, request, *args, **kwargs):
        """删除梦境 - 标记关联图片为待删除"""
        instance = self.get_object()
        
        try:
            # 在删除梦境前，处理关联的图片
            image_manager = ImageLifecycleManager(request.user)
            
            # 提取梦境中的所有图片URL
            image_urls = image_manager.extract_image_urls_from_html(instance.content)
            
            # 标记所有相关图片为待删除
            for url in image_urls:
                image_manager._mark_image_for_deletion(url)
            
        except Exception as e:
            import logging
            logger = logging.getLogger(__name__)
            logger.error(f"删除梦境时图片处理失败: {e}")
        
        # 删除梦境实例
        self.perform_destroy(instance)
        return Response(status=status.HTTP_204_NO_CONTENT)

    @action(detail=True, methods=['post'])
    def toggle_favorite(self, request, pk=None):
        """切换梦境收藏状态"""
        dream = self.get_object()
        dream.is_favorite = not dream.is_favorite
        dream.save(update_fields=['is_favorite'])
        
        serializer = self.get_serializer(dream)
        return Response(serializer.data)

    @action(detail=False)
    def favorites(self, request):
        """获取收藏的梦境列表"""
        queryset = self.get_queryset().filter(is_favorite=True)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = DreamListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DreamListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def recurring(self, request):
        """获取重复梦境列表"""
        queryset = self.get_queryset().filter(is_recurring=True)
        page = self.paginate_queryset(queryset)
        
        if page is not None:
            serializer = DreamListSerializer(page, many=True)
            return self.get_paginated_response(serializer.data)
        
        serializer = DreamListSerializer(queryset, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def statistics(self, request):
        """获取梦境统计信息"""
        queryset = self.get_queryset()
        total_dreams = queryset.count()
        lucid_dreams = queryset.filter(lucidity_level__gte=3).count()
        favorite_dreams = queryset.filter(is_favorite=True).count()
        recurring_dreams = queryset.filter(is_recurring=True).count()
        
        return Response({
            'total_dreams': total_dreams,
            'lucid_dreams': lucid_dreams,
            'favorite_dreams': favorite_dreams,
            'recurring_dreams': recurring_dreams,
        })

    @action(detail=False)
    def categories(self, request):
        """获取可用的梦境分类"""
        categories = DreamCategory.objects.all()
        serializer = DreamCategorySerializer(categories, many=True)
        return Response(serializer.data)

    @action(detail=False)
    def tags(self, request):
        """获取用户的标签"""
        user = request.user
        tags = Tag.objects.filter(
            models.Q(created_by=user) | models.Q(is_public=True)
        ).distinct()
        serializer = TagSerializer(tags, many=True)
        return Response(serializer.data)

    @action(detail=False, methods=['get'])
    def image_stats(self, request):
        """获取用户的图片统计信息"""
        try:
            from ..models import UploadedImage
            
            total_images = UploadedImage.objects.filter(user=request.user).count()
            active_images = UploadedImage.objects.filter(user=request.user, status='active').count()
            pending_delete = UploadedImage.objects.filter(user=request.user, status='pending_delete').count()
            
            return Response({
                'total_images': total_images,
                'active_images': active_images,
                'pending_delete_images': pending_delete,
            })
            
        except Exception as e:
            return Response(
                {'error': f'获取图片统计失败: {str(e)}'}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

    # 私有方法
    def _extract_form_data(self, request):
        """从请求中提取表单数据"""
        form_data = {}
        
        # 文本字段
        text_fields = [
            'title', 'content', 'interpretation', 'personal_notes',
            'dream_date', 'lucidity_level', 'mood_before_sleep', 
            'mood_in_dream', 'mood_after_waking', 'sleep_quality',
            'sleep_duration', 'bedtime', 'wake_time', 'is_recurring',
            'recurring_elements', 'vividness',
            'privacy', 'is_favorite'
        ]
        
        for field in text_fields:
            value = request.data.get(field)
            if value is not None and value != '':
                form_data[field] = value
        
        # JSON字段
        json_fields = ['categories', 'tags', 'related_dream_ids']
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
                    form_data[field] = [] if field != 'tags' else {}
        
        return form_data

    def _insert_images_to_content(self, dream):
        """插入图片到内容中"""
        return dream.content


class DreamJournalViewSet(viewsets.ModelViewSet):
    """梦境日记本视图集"""
    serializer_class = DreamJournalSerializer
    permission_classes = [permissions.IsAuthenticated]
    
    def get_queryset(self):
        return DreamJournal.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)


class SleepPatternViewSet(viewsets.ModelViewSet):
    """睡眠模式视图集"""
    serializer_class = SleepPatternSerializer
    permission_classes = [permissions.IsAuthenticated]
    ordering = ['-date']
    
    def get_queryset(self):
        return SleepPattern.objects.filter(user=self.request.user)
    
    def perform_create(self, serializer):
        serializer.save(user=self.request.user)
