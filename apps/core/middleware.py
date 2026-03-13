from django.utils import translation
from django.utils.deprecation import MiddlewareMixin
from django.conf import settings

class LanguageMiddleware(MiddlewareMixin):
    def process_request(self, request):
        language = None
        
        if request.user.is_authenticated:
            language = request.user.preferred_language
        
        if not language and 'lang' in request.GET:
            lang = request.GET.get('lang')
            if lang in [code for code, _ in settings.LANGUAGES]:
                language = lang
        
        if not language:
            language = translation.get_language_from_request(request)
        
        if not language:
            language = settings.LANGUAGE_CODE
        
        translation.activate(language)
        request.LANGUAGE_CODE = language