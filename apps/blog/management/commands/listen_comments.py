import asyncio
import json
import aioredis
from django.core.management.base import BaseCommand
from django.conf import settings

class Command(BaseCommand):
    help = 'Async Redis listener for comments channel'
    
    def handle(self, *args, **options):

        self.stdout.write('Starting async comment listener...')
        asyncio.run(self.listen_async())
    
    async def listen_async(self):
        redis = None
        try:
            redis = await aioredis.from_url(
                settings.CACHES['default']['LOCATION'],
                decode_responses=True
            )
            
            pubsub = redis.pubsub()
            await pubsub.subscribe('comments')
            
            self.stdout.write(self.style.SUCCESS('Listening for comments (async)...'))
            
            async for message in pubsub.listen():
                if message['type'] == 'message':
                    try:
                        data = json.loads(message['data'])
                        self.stdout.write(
                            self.style.SUCCESS(
                                f'\nNew comment on "{data["post_title"]}":\n'
                                f'Author ID: {data["author_id"]}\n'
                                f'Post slug: {data["post_slug"]}\n'
                                f'Comment: {data["comment"]}\n'
                                f'Time: {data["created_at"]}\n'
                                f'{"="*50}'
                            )
                        )
                    except json.JSONDecodeError as e:
                        self.stdout.write(
                            self.style.ERROR(f'Invalid JSON received: {e}')
                        )
                    except KeyError as e:
                        self.stdout.write(
                            self.style.ERROR(f'Missing key in message: {e}')
                        )
                    except Exception as e:
                        self.stdout.write(
                            self.style.ERROR(f'Error processing message: {e}')
                        )
                        
        except aioredis.ConnectionError as e:
            self.stdout.write(
                self.style.ERROR(f'Redis connection error: {e}')
            )
        except Exception as e:
            self.stdout.write(
                self.style.ERROR(f'Unexpected error: {e}')
            )
        finally:
            if redis:
                await redis.close()
                self.stdout.write('Redis connection closed.')