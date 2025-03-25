from rest_framework import serializers
from dream.models import Dream, DreamCategory, Tag, DreamImage


# 梦境图片序列化器
class DreamImageSerializer(serializers.ModelSerializer):
    """梦境图片序列化器"""

    class Meta:
        model = DreamImage
        fields = ['id', 'image_url', 'position', 'created_at']


# 标签序列化器
class TagSerializer(serializers.ModelSerializer):
    """标签序列化器"""

    class Meta:
        model = Tag
        fields = ['id', 'name', 'tag_type']


# 梦境分类序列化器
class DreamCategorySerializer(serializers.ModelSerializer):
    """梦境分类序列化器"""
    display_name = serializers.SerializerMethodField()

    class Meta:
        model = DreamCategory
        fields = ['id', 'name', 'display_name']

    def get_display_name(self, obj):
        return obj.get_name_display()


# 梦境序列化器
class DreamSerializer(serializers.ModelSerializer):
    """梦境序列化器"""
    categories = DreamCategorySerializer(many=True, read_only=True)
    tags = serializers.SerializerMethodField()
    images = DreamImageSerializer(many=True, read_only=True)
    author = serializers.SerializerMethodField()

    class Meta:
        model = Dream
        fields = [
            'id', 'title', 'content', 'author', 'categories', 'tags', 'images', 'created_at', 'updated_at'
        ]

    def get_author(self, obj):
        return {
            'id': obj.user.id,
            'username': obj.user.username
        }

    def get_tags(self, obj):
        """将不同类型的标签组织成嵌套结构，只返回标签名"""
        return {
            'theme': [tag.name for tag in obj.theme_tags.all()],
            'character': [tag.name for tag in obj.character_tags.all()],
            'location': [tag.name for tag in obj.location_tags.all()],
        }


# 梦境创建序列化器
class DreamCreateSerializer(serializers.ModelSerializer):
    """梦境创建序列化器"""
    categories = serializers.ListField(
        child=serializers.CharField(max_length=50),
        write_only=True
    )
    theme_tags = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False
    )
    character_tags = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False
    )
    location_tags = serializers.ListField(
        child=serializers.CharField(max_length=20),
        write_only=True,
        required=False
    )
    images = serializers.ListField(
        child=serializers.DictField(),
        write_only=True,
        required=False
    )

    class Meta:
        model = Dream
        fields = [
            'title', 'content', 'categories',
            'theme_tags', 'character_tags', 'location_tags', 'images'
        ]
