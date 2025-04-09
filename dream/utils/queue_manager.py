import base64
import logging
from typing import List, Dict

logger = logging.getLogger(__name__)

def send_image_processing_task(dream_id: int, image_files: List[Dict], positions: List[int]):
    """
    发送图片处理任务到Celery队列
    
    Args:
        dream_id: 梦境记录ID
        image_files: 图片文件列表 [{'name': 'xxx.jpg', 'data': binary_data}, ...]
        positions: 图片位置列表
    """
    try:
        from dream.tasks.image_tasks import process_and_upload_images
        
        # 编码图片数据
        encoded_files = []
        for file in image_files:
            encoded_files.append({
                'name': file['name'],
                'data': base64.b64encode(file['data']).decode('utf-8')
            })
        
        # 通过Celery发送任务
        result = process_and_upload_images.delay(dream_id, encoded_files, positions)
        
        logger.info(f"已将图片处理任务发送到Celery队列: dream_id={dream_id}, images={len(image_files)}, task_id={result.id}")
        return result.id
        
    except Exception as e:
        logger.error(f"发送图片处理任务失败: {str(e)}")
        raise 