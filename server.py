from maxrubika import Bot
import aiohttp
import requests
import os
import asyncio
import hashlib
import json
import re
import time
from datetime import datetime
from bs4 import BeautifulSoup
from urllib.parse import urljoin

TOKEN = "BBEHCI0FNGWLLAVDSYNAWXPNNQQCIFJRWWEVWQMIOMUIAEUSWKWUSZEGONVXDSNG"
CHANNEL_ID = "c0D6VJV0ac83df9b34cbe1082090a750"
SIGNATURE = "\n\n🆔📢 @VIPNEVS"
SEEN_FILE = "seen_newns.json"

bot = Bot(TOKEN)

NEWS_SOURCES = [
    # منابع قبلی
    {"name": "📣 SNN.ir", "url": "https://snn.ir/", "selector": "h2, h3, .title, .news-title"},
    {"name": "📣 خبرفوری", "url": "https://www.khabarfoori.com/", "selector": "h2, h3, .title, .news-title"},
    {"name": "📣 ایسنا", "url": "https://www.isna.ir/", "selector": "h2, h3, .title, .news-title"},
    {"name": "📣 تسنیم", "url": "https://www.tasnimnews.com/", "selector": "h2, h3, .title, .news-title"},
    {"name": "📣 مهرنیوز", "url": "https://www.mehrnews.com/", "selector": "h2, h3, .title"},
    {"name": "📣 تابناک", "url": "https://www.tabnak.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 عصر ایران", "url": "https://www.asriran.com/", "selector": "h2, h3, .title, .news-title"},
    {"name": "📣 فرارو", "url": "https://fararu.com/", "selector": "h2, h3, .title"},
    {"name": "📣 خبرآنلاین", "url": "https://www.khabaronline.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 ایرنا", "url": "https://www.irna.ir/", "selector": "h2, h3, .news-title"},
    {"name": "📣 مشرق نیوز", "url": "https://www.mashreghnews.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 انتخاب", "url": "https://www.entekhab.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 خبرنگاران جوان", "url": "https://www.yjc.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 همشهری", "url": "https://www.hamshahrionline.ir/", "selector": "h2, h3, .title"},
    {"name": "📣 آخرین خبر", "url": "https://akharinkhabar.ir/", "selector": "h2, h3, .title"},
    
    # منابع جدید تکنولوژی
    {"name": "📱 گجت نیوز", "url": "https://gadgetnews.net", "selector": "h2, h3, .entry-title, .post-title"},
    {"name": "📱 دیجیاتو", "url": "https://digiato.com", "selector": "h2, h3, .post-title, .entry-title, .news-title"},
    {"name": "📱 زومیت", "url": "https://www.zoomit.ir", "selector": "h2, h3, .post-title, .entry-title, .news-title"},
]

seen_hashes = {}

def load_seen_news():
    global seen_hashes
    if os.path.exists(SEEN_FILE):
        try:
            with open(SEEN_FILE, 'r', encoding='utf-8') as f:
                seen_hashes = json.load(f)
        except:
            seen_hashes = {}
    return seen_hashes

def save_seen_news():
    global seen_hashes
    if len(seen_hashes) > 2000:
        items = list(seen_hashes.items())
        seen_hashes = dict(items[-2000:])
    with open(SEEN_FILE, 'w', encoding='utf-8') as f:
        json.dump(seen_hashes, f, ensure_ascii=False, indent=2)

def extract_media_from_article(url):
    """استخراج فیلم یا عکس از صفحه خبر - اولویت با فیلم"""
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(url, headers=headers, timeout=10)
        soup = BeautifulSoup(response.content, 'html.parser')
        
        # 1. اول فیلم رو بررسی کن
        video_tags = soup.find_all('video')
        for video in video_tags:
            src = video.get('src')
            if not src:
                source = video.find('source')
                if source:
                    src = source.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(url, src)
                return {"type": "video", "url": src}
        
        # ویدئو در iframe
        iframes = soup.find_all('iframe', src=re.compile(r'(youtube|aparat|telegram|video)', re.I))
        for iframe in iframes:
            src = iframe.get('src')
            if src:
                if not src.startswith('http'):
                    src = urljoin(url, src)
                return {"type": "video", "url": src}
        
        # 2. اگر فیلم نبود، عکس رو بگیر
        og_image = soup.find('meta', property='og:image')
        if og_image and og_image.get('content'):
            img_url = og_image['content']
            if not img_url.startswith('http'):
                img_url = urljoin(url, img_url)
            return {"type": "image", "url": img_url}
        
        image_selectors = [
            'img[class*="news"]',
            'img[class*="main"]',
            'img[class*="featured"]',
            'img[class*="thumb"]',
            'article img',
            '.content img',
            'img'
        ]
        
        for selector in image_selectors:
            elements = soup.select(selector)
            for elem in elements:
                img_url = elem.get('src')
                if img_url and not img_url.startswith('data:'):
                    if not img_url.startswith('http'):
                        img_url = urljoin(url, img_url)
                    if 'logo' not in img_url.lower() and 'icon' not in img_url.lower():
                        return {"type": "image", "url": img_url}
        
        return None
        
    except Exception as e:
        print(f"⚠️ خطا در استخراج مدیا: {e}")
        return None

def get_news_from_source(source):
    try:
        headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36'}
        response = requests.get(source["url"], headers=headers, timeout=10)
        response.encoding = 'utf-8'
        soup = BeautifulSoup(response.content, 'html.parser')
        
        selectors = source["selector"].split(", ")
        news_items = []
        
        for sel in selectors:
            for element in soup.select(sel):
                text = element.get_text(strip=True)
                if text and 20 < len(text) < 250:
                    link = None
                    parent = element.find_parent('a')
                    if parent and parent.get('href'):
                        link = parent['href']
                    elif element.find('a'):
                        link = element.find('a').get('href')
                    
                    if link:
                        if not link.startswith('http'):
                            link = urljoin(source["url"], link)
                        
                        news_hash = hashlib.md5(f"{source['name']}_{text}_{link}".encode()).hexdigest()
                        news_items.append({
                            "hash": news_hash,
                            "text": text,
                            "link": link,
                            "source": source["name"],
                            "time": datetime.now().strftime("%H:%M:%S"),
                            "date": datetime.now().strftime("%Y-%m-%d")
                        })
        
        unique = {}
        for item in news_items:
            if item["text"] not in unique:
                unique[item["text"]] = item
        return list(unique.values())[:3]
    except Exception as e:
        print(f"⚠️ خطا در {source['name']}: {str(e)[:50]}")
        return []

def build_caption(news_item):
    """ساخت کپشن با تاریخ و زمان خوشگل"""
    # تبدیل زمان به فرمت خوشگل
    time_str = news_item['time']
    date_str = news_item['date']
    
    # تبدیل تاریخ به فرمت شمسی خوشگل
    date_parts = date_str.split('-')
    if len(date_parts) == 3:
        year = date_parts[0]
        month = date_parts[1]
        day = date_parts[2]
        
        # تبدیل ماه به اسم
        month_names = {
            '01': 'دی', '02': 'بهمن', '03': 'اسفند',
            '04': 'فروردین', '05': 'اردیبهشت', '06': 'خرداد',
            '07': 'تیر', '08': 'مرداد', '09': 'شهریور',
            '10': 'مهر', '11': 'آبان', '12': 'آذر'
        }
        month_name = month_names.get(month, month)
        date_str = f"{int(day)} {month_name} {year}"
    
    caption = f"""{news_item['source']}

🔷 {news_item['text']}

[{news_item['source']}]({news_item['link']})

🕐 {time_str} - {date_str}{SIGNATURE}"""
    
    return caption

async def send_media_to_channel(media_url, media_type, caption, chat_id):
    """ارسال فیلم یا عکس با maxrubika"""
    
    if media_type == "video":
        temp_file = f"temp_video_{int(time.time())}.mp4"
    else:
        temp_file = f"temp_image_{int(time.time())}.jpg"
    
    try:
        async with aiohttp.ClientSession() as session:
            async with session.get(media_url) as response:
                if response.status == 200:
                    content = await response.read()
                    
                    with open(temp_file, "wb") as f:
                        f.write(content)
                    
                    if media_type == "video":
                        await bot.send_video(
                            chat_id=chat_id,
                            video=temp_file,
                            text=caption
                        )
                    else:
                        await bot.send_image(
                            chat_id=chat_id,
                            image=temp_file,
                            text=caption
                        )
                    
                    os.remove(temp_file)
                    return True
                else:
                    return False
    except Exception as e:
        print(f"⚠️ خطا در ارسال {media_type}: {e}")
        if os.path.exists(temp_file):
            os.remove(temp_file)
        return False

async def send_news_to_channel(news_item):
    """ارسال فیلم یا عکس با کپشن"""
    
    media = extract_media_from_article(news_item["link"])
    caption = build_caption(news_item)
    
    if media and media.get("url"):
        media_type = media.get("type")
        media_url = media.get("url")
        
        emoji = "🎬" if media_type == "video" else "🖼️"
        print(f"{emoji} {media_type} پیدا شد: {media_url[:50]}...")
        
        success = await send_media_to_channel(media_url, media_type, caption, CHANNEL_ID)
        
        if success:
            print(f"✅ {news_item['source']} [{media_type}+کپشن]: {news_item['text'][:35]}...")
            return True
        else:
            print(f"⚠️ ارسال {media_type} ناموفق، ارسال متن...")
            await bot.send_message(CHANNEL_ID, caption)
            return True
    else:
        print(f"📝 مدیا پیدا نشد، ارسال متن...")
        await bot.send_message(CHANNEL_ID, caption)
        return True

@bot.on_command("start")
async def start_handler(bot, event):
    await event.reply(
        "🤖 *ربات خبری هوشمند فعال شد!*\n\n"
        f"🌐 {len(NEWS_SOURCES)} منبع خبری\n"
        "📱 پشتیبانی از اخبار تکنولوژی\n"
        "🎬 ارسال فیلم با کپشن\n"
        "🖼️ ارسال عکس با کپشن\n"
        "🔗 لینک به صورت [VIPZEXNET](https://VIPZEXNET.ir)\n"
        "📆 تاریخ و زمان خوشگل\n"
        "♦ خلاصه خبر\n"
        "🔷 عنوان خبر\n\n"
        "📢 @VIPNEVS"
    )

load_seen_news()

async def news_checker():
    print("=" * 55)
    print("🤖 ربات خبری با maxrubika - فیلم و عکس با کپشن!")
    print(f"📢 کانال: {CHANNEL_ID}")
    print(f"🌐 تعداد منابع: {len(NEWS_SOURCES)}")
    print("🎬 ارسال فیلم با کپشن")
    print("🖼️ ارسال عکس با کپشن")
    print("📱 پشتیبانی از اخبار تکنولوژی (گجت نیوز، دیجیاتو، زومیت)")
    print("🔗 لینک به صورت [VIPZEXNET](https://VIPZEXNET.ir)")
    print("📆 تاریخ و زمان خوشگل")
    print("⏰ هر 20 ثانیه چک می‌شود...")
    print("=" * 55)
    
    global seen_hashes
    
    while True:
        try:
            print(f"\n🔄 چک کردن - {datetime.now().strftime('%H:%M:%S')}")
            new_count = 0
            
            for source in NEWS_SOURCES:
                news_list = get_news_from_source(source)
                
                for news in news_list:
                    if news["hash"] not in seen_hashes:
                        if await send_news_to_channel(news):
                            seen_hashes[news["hash"]] = news
                            save_seen_news()
                            new_count += 1
                            await asyncio.sleep(3)
            
            if new_count == 0:
                print("📭 خبر جدیدی نیست")
            else:
                print(f"✨ {new_count} خبر جدید ارسال شد")
            
            await asyncio.sleep(20)
            
        except Exception as e:
            print(f"❌ خطای کلی: {e}")
            await asyncio.sleep(10)

async def main():
    await asyncio.gather(
        asyncio.to_thread(bot.run),
        news_checker()
    )

if __name__ == "__main__":
    asyncio.run(main())