import os
from dotenv import load_dotenv

load_dotenv()

TOKEN = os.environ['BOT_TOKEN']
ADMIN_ID = int(os.environ.get('ADMIN_ID', '0'))
CARD_NUMBER = os.environ.get('CARD_NUMBER', 'XXXX-XXXX-XXXX-XXXX')
CARD_OWNER = os.environ.get('CARD_OWNER', 'نام شما')
CHANNEL_ID = os.environ.get('CHANNEL_ID', '@mychannel')
POST_TRACKING_URL = "https://tracking.post.ir/?code="