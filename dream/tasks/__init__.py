# 在这里导入所有任务
# 注意：避免循环导入问题，在模块被导入时不要执行代码

# 只在被显式导入时才导出任务
__all__ = ['process_and_upload_images']

# 在需要使用时导入任务
def _import_tasks():
    """延迟导入所有任务"""
    global process_and_upload_images
    from .image_tasks import process_and_upload_images  # noqa

# 预先声明导出的函数
process_and_upload_images = None

# 执行导入
_import_tasks() 