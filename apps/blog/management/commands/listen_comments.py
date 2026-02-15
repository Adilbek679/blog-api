import redis
import json
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Listen to Redis comments channel and print messages'
    
    def handle(self, *args, **options):
        self.stdout.write('Starting comment listener...')
        
        r = redis.Redis.from_url(settings.CACHES['default']['LOCATION'])
        pubsub = r.pubsub()
        pubsub.subscribe('comments')
        
        self.stdout.write('Listening for comments...')
        
        for message in pubsub.listen():
            if message['type'] == 'message':
                try:
                    data = json.loads(message['data'].decode())
                    self.stdout.write(
                        self.style.SUCCESS(
                            f'\nNew comment on "{data["post_title"]}":\n'
                            f'Author: {data["author"]}\n'
                            f'Comment: {data["comment"]}\n'
                            f'Time: {data["created_at"]}\n'
                            f'{"="*50}'
                        )
                    )
                except Exception as e:
                    self.stdout.write(
                        self.style.ERROR(f'Error processing message: {e}')
                    )