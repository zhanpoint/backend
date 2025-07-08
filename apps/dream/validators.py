import re
from django.core.exceptions import ValidationError
from django.utils.translation import gettext as _


class ComplexPasswordValidator:
    """
    自定义密码验证器: 验证密码至少包含一个大写字母、一个小写字母和一个数字
    """

    def __init__(self, min_length=8, max_length=32):
        self.min_length = min_length
        self.max_length = max_length

    def validate(self, password, user=None):
        # 验证密码长度
        if len(password) < self.min_length:
            raise ValidationError(
                _("密码太短，至少需要 %(min_length)d 个字符。"),
                code='password_too_short',
                params={'min_length': self.min_length},
            )
        if len(password) > self.max_length:
            raise ValidationError(
                _("密码太长，最多允许 %(max_length)d 个字符。"),
                code='password_too_long',
                params={'max_length': self.max_length},
            )

        # 验证是否包含至少一个大写字母
        if not re.search(r'[A-Z]', password):
            raise ValidationError(
                _("密码必须包含至少一个大写字母。"),
                code='password_no_upper',
            )

        # 验证是否包含至少一个小写字母
        if not re.search(r'[a-z]', password):
            raise ValidationError(
                _("密码必须包含至少一个小写字母。"),
                code='password_no_lower',
            )

        # 验证是否包含至少一个数字
        if not re.search(r'[0-9]', password):
            raise ValidationError(
                _("密码必须包含至少一个数字。"),
                code='password_no_digit',
            )

    def get_help_text(self):
        return _(
            "您的密码必须包含：\n"
            "- 长度在8到32个字符之间\n"
            "- 至少一个大写字母\n"
            "- 至少一个小写字母\n"
            "- 至少一个数字"
        )
