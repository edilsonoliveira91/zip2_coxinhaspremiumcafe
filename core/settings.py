import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from decouple import config

# Carrega as variáveis de ambiente
load_dotenv()

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Gerencia as apps do projeto dentro da pasta apps
sys.path.insert(0, str(BASE_DIR / 'apps'))

# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY', default='sua-chave-de-desenvolvimento')
DEBUG = config('DEBUG', default=False, cast=bool)
OFFLINE_MODE = config('OFFLINE_MODE', default=False, cast=bool)

if DEBUG or OFFLINE_MODE:
    ALLOWED_HOSTS = ['*']
else:
    ALLOWED_HOSTS = [
        'zip2coxinhaspremiumcafe-production.up.railway.app',
        'coxinhaspremiumcafe.zip2.com.br',
        'www.coxinhaspremiumcafe.zip2.com.br',
    ]

    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
    SECURE_BROWSER_XSS_FILTER = True
    SECURE_CONTENT_TYPE_NOSNIFF = True

CSRF_TRUSTED_ORIGINS = [
    'https://zip2coxinhaspremiumcafe-production.up.railway.app',
    'https://coxinhaspremiumcafe.zip2.com.br',
    'https://www.coxinhaspremiumcafe.zip2.com.br',
    'https://*.railway.app',
]


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Tailwind
    'tailwind',
    'theme',

    # My apps
    'utils',
    'accounts',
    'orders',
    'products',
    'checkouts',
    'pinpads',
    'financials',
    'companys',
    'reports',
    'config',
    'kiosk',
    'banks',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware', 
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'banks.context_processors.bank_access',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

# Database
if DEBUG:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.sqlite3',
            'NAME': BASE_DIR / 'db.sqlite3',
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('PGDATABASE'),
            'USER': config('PGUSER'),
            'PASSWORD': config('PGPASSWORD'),
            'HOST': config('PGHOST'),
            'PORT': config('PGPORT'),
        }
    }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'pt-br'

TIME_ZONE = 'America/Sao_Paulo'

USE_I18N = True

USE_L10N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)
STATIC_URL = '/static/'
STATICFILES_DIRS = [
    BASE_DIR / 'templates' / 'static',
]
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

IMAGE_UPLOAD_MAX_MB = config('IMAGE_UPLOAD_MAX_MB', default=8, cast=int)

# Configurações do Tailwind
TAILWIND_APP_NAME = 'theme'

# INTERNAL_IPS apenas em desenvolvimento
if DEBUG:
    INTERNAL_IPS = ['127.0.0.1']

#====================================================
# STORAGE: estático via Whitenoise; mídia padrão local (Railway Volume)
# Imagens usam R2 via storage por campo (model fields).
#====================================================
USE_R2_STORAGE = config('USE_R2_STORAGE', default=False, cast=bool)

if not DEBUG:
    WHITENOISE_MIMETYPES = {
        '.js': 'application/javascript',
        '.css': 'text/css',
    }
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'whitenoise.storage.CompressedManifestStaticFilesStorage',
        },
    }
else:
    STORAGES = {
        'default': {
            'BACKEND': 'django.core.files.storage.FileSystemStorage',
        },
        'staticfiles': {
            'BACKEND': 'django.contrib.staticfiles.storage.StaticFilesStorage',
        },
    }

if USE_R2_STORAGE:
    AWS_ACCESS_KEY_ID = config('R2_ACCESS_KEY_ID')
    AWS_SECRET_ACCESS_KEY = config('R2_SECRET_ACCESS_KEY')
    AWS_STORAGE_BUCKET_NAME = config('R2_BUCKET_NAME')
    AWS_S3_ENDPOINT_URL = config('R2_ENDPOINT_URL')
    AWS_S3_REGION_NAME = 'auto'
    AWS_DEFAULT_ACL = None
    AWS_S3_SIGNATURE_VERSION = 's3v4'
    AWS_QUERYSTRING_AUTH = False
    _r2_public = config('R2_PUBLIC_URL').replace('https://', '').replace('http://', '').strip('/')
    AWS_S3_CUSTOM_DOMAIN = _r2_public

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Configuração do modelo de usuário customizado
AUTH_USER_MODEL = 'accounts.User'

# Configurações de autenticação
LOGIN_URL = 'accounts:login'
LOGIN_REDIRECT_URL = 'accounts:dashboard'
LOGOUT_REDIRECT_URL = 'accounts:login'


#====================================================
# CONFIGURAÇOES DO PINPAD - REDE ITAÚ
#====================================================
# Configurações da REDE Itaú
REDE_SANDBOX = config('REDE_SANDBOX', default=True, cast=bool)
REDE_PV = config('REDE_PV', default='')  # Número de filiação
REDE_INTEGRATION_KEY = config('REDE_INTEGRATION_KEY', default='')  # Chave de integração

#====================================================
# CONFIGURAÇÕES DA IMPRESSORA DE REDE (RawBT / p910nd)
#====================================================
PRINTER_NETWORK_IP = config('PRINTER_NETWORK_IP', default='192.168.10.184')
PRINTER_NETWORK_PORT = config('PRINTER_NETWORK_PORT', default=9100, cast=int)

# Configurações de logging para payment providers
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'file': {
            'level': 'INFO',
            'class': 'logging.FileHandler',
            'filename': BASE_DIR / 'logs' / 'payment_providers.log',
        },
        'console': {
            'level': 'DEBUG' if DEBUG else 'INFO',
            'class': 'logging.StreamHandler',
        },
    },
    'loggers': {
        'django.request': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'django': {
            'handlers': ['console'],
            'level': 'ERROR',
            'propagate': False,
        },
        'utils.image_optimizer': {
            'handlers': ['console'],
            'level': 'INFO',
            'propagate': False,
        },
        'pinpads.services': {
            'handlers': ['file', 'console'],
            'level': 'INFO',
            'propagate': False,
        },
    },
}

# Criar diretório de logs se não existir
import os
os.makedirs(BASE_DIR / 'logs', exist_ok=True)