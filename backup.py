import discord
from discord.ext import commands
import yt_dlp as youtube_dl
import asyncio
import logging
import config  # Tetap menggunakan config.py Anda
import random
import requests
import json
import textwrap
from difflib import get_close_matches
from datetime import datetime

# ======================================================
# 💡 IMPORT AUTO-VOICE
# ======================================================
from cogs.auto_voice import (
    setup_auto_voice_events,
    setup_persistent_interface,
    VoiceControlViewGlobal
)

logging.basicConfig(level=logging.INFO)

intents = discord.Intents.default()
intents.guilds = True
intents.voice_states = True
intents.members = True
intents.message_content = True

bot = commands.Bot(command_prefix=lambda bot, message: 'lacus ', intents=intents)
afk_users = {}
# ======================================================
# Logika ChatBot Backend(JSON)
# ======================================================
DATABASE_FILE = 'data.json'
CONFIDENCE_THRESHOLD = 0.6

def load_knowledge_base(file_path: str) -> dict:
    """Membaca database JSON dengan error handling"""
    try:
        with open(file_path, 'r') as file:
            return json.load(file)
    except (FileNotFoundError, json.JSONDecodeError):
        return {"questions": []}

def save_knowledge_base(file_path: str, data: dict):
    """Menulis ulang database dengan data baru"""
    with open(file_path, 'w') as file:
        json.dump(data, file, indent=4)

def find_best_match(user_question: str, questions: list):
    """Mencari kemiripan teks menggunakan difflib"""
    matches = get_close_matches(user_question, questions, n=1, cutoff=CONFIDENCE_THRESHOLD)
    return matches[0] if matches else None

def get_answer_for_question(question: str, knowledge_base: dict) -> str | None:
    for q in knowledge_base["questions"]:
        if q["question"] == question:
            return q["answer"]
    return None
# ======================================================
# SETUP YTDL
# ======================================================

ytdl_format_options = {
    'format': 'bestaudio/best',
    'outtmpl': '%(extractor)s-%(id)s-%(title)s.%(ext)s',
    'restrictfilenames': True,
    'noplaylist': False,
    'nocheckcertificate': True,
    'ignoreerrors': False,
    'logtostderr': False,
    'quiet': True,
    'no_warnings': True,
    'default_search': 'auto',
    'source_address': '0.0.0.0'
}
ffmpeg_options = {'options': '-vn'}
ytdl = youtube_dl.YoutubeDL(ytdl_format_options)

queues = {}

def get_queue(ctx):
    if ctx.guild.id not in queues:
        queues[ctx.guild.id] = []
    return queues[ctx.guild.id]


# ======================================================
# EVENT SETUP_HOOK
# ======================================================
@bot.event
async def setup_hook():
    """Mendaftarkan semua view persisten saat bot startup."""
    
    bot.add_view(VoiceControlViewGlobal(bot))
    print("✅ [INFO] Persistent View (VoiceControlViewGlobal) telah didaftarkan.")


# ======================================================
# EVENT ON_READY
# ======================================================

@bot.event
async def on_ready():
    """Event utama yang menampilkan status bot dan sync command"""
    print(f'✅ Logged in as {bot.user} ({bot.user.id})')

    activity = discord.Streaming(
        name="OFFICIAL WAIFU NOUFAL ZAIDAAN",
        url="https://twitch.tv/fal0_"
    )
    await bot.change_presence(status=discord.Status.online, activity=activity)
    print("✅ [INFO] Status bot diatur ke 'Streaming'.")

    try:
        synced = await bot.tree.sync()
        print(f"✅ [INFO] Synced {len(synced)} slash command(s).")
    except Exception as e:
        print(f"❌ [ERROR] Gagal syncing commands: {e}")

    await setup_persistent_interface(bot)


# ======================================================
# KELAS AUDIO
# ======================================================
class YTDLSource(discord.PCMVolumeTransformer):
    def __init__(self, source, *, data, volume=0.5):
        super().__init__(source, volume)
        self.data = data
        self.title = data.get('title')
        self.url = data.get('url')

    @classmethod
    async def from_url(cls, url, *, loop=None, stream=False):
        loop = loop or asyncio.get_event_loop()
        data = await loop.run_in_executor(None, lambda: ytdl.extract_info(url, download=not stream))

        if 'entries' in data:
            return [cls(discord.FFmpegPCMAudio(ytdl.prepare_filename(entry), **ffmpeg_options), data=entry) for entry in data['entries']]

        filename = data['url'] if stream else ytdl.prepare_filename(data)
        return [cls(discord.FFmpegPCMAudio(filename, **ffmpeg_options), data=data)]


# ======================================================
# PERINTAH DASAR
# ======================================================

# --- 💡 PERINTAH CUACA DIPERBAIKI DENGAN API BARU 💡 ---
@bot.command()
async def cuaca(ctx, *, city: str = None):
    """Menampilkan cuaca untuk kota yang spesifik menggunakan wttr.in"""
    
    if city is None:
        await ctx.send("❌ Kamu lupa memasukkan nama kota! Contoh: `lacus cuaca Jakarta`")
        return

    # 1. Definisikan fungsi blocking (sync) yang akan kita jalankan
    def fetch_weather_sync(city_name):
        try:
            # --- URL API BARU (wttr.in) ---
            url = f"https://wttr.in/{city_name}?format=j1"
            # Beberapa API menghargai User-Agent
            headers = {'User-Agent': 'Mozilla/5.0'}
            response = requests.get(url, headers=headers, timeout=10)
            
            # Ini akan error jika kota tidak ditemukan (404) atau server error (500)
            response.raise_for_status() 
            return response.json()
        
        except requests.exceptions.RequestException as e:
            # Menangkap error 404, 500, timeout, dan koneksi
            logging.error(f"Request error in weather API (wttr.in): {e}")
            return None # Return None jika kota tidak ditemukan atau API error

    try:
        # Menampilkan "Bot is typing..."
        async with ctx.typing():
            # 2. Jalankan fungsi blocking di thread terpisah
            data = await asyncio.to_thread(fetch_weather_sync, city)

        # 3. Proses data
        if data is None:
            await ctx.send(f"❌ Maaf, tidak bisa menemukan cuaca untuk **{city}**. Pastikan nama kota benar.")
            return

        # 4. Ekstrak data (Struktur BARU untuk wttr.in)
        current = data['current_condition'][0]
        area = data['nearest_area'][0]
        
        city_name = area['areaName'][0]['value']
        temperature = current['temp_C']
        feels_like = current['FeelsLikeC'] # Data baru yang menarik
        description = current['weatherDesc'][0]['value']
        humidity = current['humidity']
        wind_speed = current['windspeedKmph']
        
        embed = discord.Embed(
            title=f"🌤 Cuaca di {city_name}",
            description=f"{description}",
            color=0x0080ff
        )
        embed.add_field(name="🌡 Suhu", value=f"{temperature}°C", inline=True)
        embed.add_field(name="🌡 Terasa Seperti", value=f"{feels_like}°C", inline=True)
        embed.add_field(name="💧 Kelembapan", value=f"{humidity}%", inline=True)
        embed.add_field(name="💨 Kecepatan Angin", value=f"{wind_speed} km/h", inline=True)
        embed.set_footer(text="Data cuaca diperoleh dari wttr.in") # Footer diubah
        
        await ctx.send(embed=embed)
        
    except Exception as e:
        # Ini menangkap error jika struktur JSON-nya aneh
        await ctx.send("❌ Maaf, terjadi kesalahan internal saat memproses data cuaca.")
        logging.error(f"Unhandled error in 'cuaca' command: {e}")
        logging.info(f"Data yg diterima dari wttr.in: {data}") # Log data untuk debug

# --- Akhir Perbaikan ---

@bot.command()
async def ping(ctx):
    await ctx.send('Ada sayaang!')

@bot.command()
async def who(ctx):
    await ctx.send('Im fal is girlfriend')

@bot.command()
async def waifu(ctx):
    guild = ctx.guild
    embed = discord.Embed(title='Noufal Zaidaan', color=0x0080ff)
    embed.add_field(name="Kesayangannya:", value=guild.owner.mention, inline=True)
    embed.set_footer(text=f"id: {guild.id}")
    embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)


# ======================================================
# COMMAND PROFILE, SERVER, SUPPORT, DLL
# (Tidak ada perubahan)
# ======================================================
@bot.command(name="profile")
async def profile(ctx, user: discord.Member = None):
    user = user or ctx.author
    embed = discord.Embed(title=f"{user}", color=0x0080ff)
    embed.add_field(name="Mention:", value=user.mention)
    embed.add_field(name="Nick:", value=user.nick)
    embed.add_field(name="Created at:", value=user.created_at.strftime("%b %d, %Y, %T"))
    embed.add_field(name="Joined at:", value=user.joined_at.strftime("%b %d, %Y, %T"))
    embed.add_field(name="Top role:", value=user.top_role)
    embed.set_thumbnail(url=user.display_avatar.url)
    await ctx.send(embed=embed)


@bot.command(name="server")
async def server(ctx):
    guild = ctx.guild
    embed = discord.Embed(title=guild.name, color=0x0080ff)
    embed.add_field(name="Owner:", value=guild.owner.mention)
    embed.add_field(name="Channels:", value=len(guild.channels))
    embed.add_field(name="Members:", value=guild.member_count)
    embed.add_field(name="Created at:", value=guild.created_at.strftime("%b %d, %Y, %T"))
    embed.set_thumbnail(url=guild.icon.url)
    await ctx.send(embed=embed)


@bot.command()
async def support(ctx):
    embed = discord.Embed(
        title="Support Me!",
        description="Hi!, Support server ini dengan meramaikannya yaa!\n[Subscribe Youtube Channel!](https://www.youtube.com/channel/UChrOMGz38-rInAQkrU6z6hg)",
        color=discord.Color.blue()
    )
    embed.add_field(name="Komunitas kita!", value="Games, Events, Komunitas", inline=False)
    embed.set_footer(text="Terimakasih sudah menggunakan Waifu Noufal Zaidaan!")
    await ctx.send(embed=embed)


@bot.command()
async def developer(ctx):
    embed = discord.Embed(
        title="Developer",
        description="Support developer ini di sini:\n[Orang Orang Baik](https://saweria.co/NoufalZaidan)",
        color=discord.Color.blue()
    )
    await ctx.send(embed=embed)

# ======================================================
# FITUR ANIME API (JIKAN / MYANIMELIST)
# ======================================================

@bot.command(name="anime", help="Cari info anime dari MyAnimeList")
async def search_anime(ctx, *, query: str = None):
    """
    Mengambil data anime dari Jikan API v4.
    Contoh: lacus anime Naruto
    """
    if not query:
        await ctx.send("❌ Masukkan judul anime! Contoh: `lacus anime Naruto`")
        return

    async with ctx.typing():
        try:
            # Request ke Jikan API
            url = f"https://api.jikan.moe/v4/anime?q={query}&limit=1"
            response = requests.get(url)
            data = response.json()

            if not data['data']:
                await ctx.send(f"❌ Anime **{query}** tidak ditemukan.")
                return

            # Ambil hasil pertama
            anime = data['data'][0]
            
            title = anime.get('title', 'Unknown')
            title_jp = anime.get('title_japanese', '')
            score = anime.get('score', 'N/A')
            episodes = anime.get('episodes', '?')
            status = anime.get('status', 'Unknown')
            synopsis = anime.get('synopsis', 'Tidak ada sinopsis.')
            image_url = anime['images']['jpg']['large_image_url']
            url_mal = anime.get('url', '')

            # Potong sinopsis jika terlalu panjang (> 300 karakter)
            short_synopsis = textwrap.shorten(synopsis, width=300, placeholder="... (baca selengkapnya di link)")

            embed = discord.Embed(title=f"🎬 {title}", url=url_mal, color=0xff99cc)
            if title_jp:
                embed.description = f"**Japanese:** {title_jp}\n\n{short_synopsis}"
            else:
                embed.description = short_synopsis

            embed.add_field(name="⭐ Score", value=f"{score}/10", inline=True)
            embed.add_field(name="📺 Episodes", value=f"{episodes}", inline=True)
            embed.add_field(name="📡 Status", value=f"{status}", inline=True)
            embed.set_thumbnail(url=image_url)
            embed.set_footer(text="Data by Jikan (MyAnimeList)")

            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Anime API Error: {e}")
            await ctx.send("❌ Terjadi kesalahan saat mengambil data anime.")

@bot.command(name="topanime", help="Lihat top 5 anime terpopuler")
async def top_anime(ctx):
    """Menampilkan 5 anime teratas dari MyAnimeList"""
    async with ctx.typing():
        try:
            url = "https://api.jikan.moe/v4/top/anime?limit=5"
            response = requests.get(url)
            data = response.json()

            embed = discord.Embed(title="🏆 Top 5 Anime (MyAnimeList)", color=0xFFD700)
            
            description = ""
            for index, anime in enumerate(data['data'], 1):
                title = anime['title']
                score = anime.get('score', 'N/A')
                link = anime['url']
                description += f"**{index}. [{title}]({link})** - ⭐ {score}\n"

            embed.description = description
            embed.set_footer(text="Diupdate secara realtime")
            await ctx.send(embed=embed)

        except Exception as e:
            logging.error(f"Top Anime Error: {e}")
            await ctx.send("❌ Gagal mengambil data top anime.")


# ======================================================
# COMMAND CHATBOT (FITUR BARU)
# ======================================================
@bot.command(name="tanya", help="Mengobrol dengan AI Anime")
async def tanya(ctx, *, pertanyaan: str = None):
    """
    Fitur utama Chatbot: Mencari jawaban di JSON.
    Contoh: lacus tanya rekomendasi anime
    """
    if not pertanyaan:
        await ctx.send("Lacus-chan: Eh? Mau tanya apa? Ketik `lacus tanya [pertanyaanmu]` ya!")
        return

    # Load database terbaru
    knowledge_base = load_knowledge_base(DATABASE_FILE)
    question_list = [q["question"] for q in knowledge_base["questions"]]
    
    # Cari kecocokan
    best_match = find_best_match(pertanyaan.lower(), question_list)

    async with ctx.typing():
        if best_match:
            answer = get_answer_for_question(best_match, knowledge_base)
            # Respon jika ketemu
            embed = discord.Embed(description=f"{answer}", color=discord.Color.pink())
            embed.set_footer(text=f"Confidence Match: {best_match}")
            await ctx.send(embed=embed)
        else:
            # Respon jika TIDAK ketemu (Mode Belajar)
            await ctx.send(
                f"😓 Lacus-chan: Maaf, aku belum ngerti maksud kamu...\n"
                f"**Bantu ajarin aku dong!**\n"
                f"Ketik format ini:\n"
                f"`lacus ajarin {pertanyaan} | [jawaban kamu]`"
            )

@bot.command(name="ajarin", help="Mengajari AI jawaban baru")
async def ajarin(ctx, *, input_data: str = None):
    """
    Fitur Learning: Menyimpan data baru ke JSON.
    Contoh: lacus ajarin siapa namamu | namaku Lacus
    """
    if not input_data or "|" not in input_data:
        await ctx.send("⚠️ Format salah! Gunakan pemisah `|`.\nContoh: `lacus ajarin anime terbaik | Fullmetal Alchemist`")
        return

    # Memisahkan pertanyaan dan jawaban berdasarkan tanda '|'
    parts = input_data.split("|", 1)
    question = parts[0].strip().lower()
    answer = parts[1].strip()

    knowledge_base = load_knowledge_base(DATABASE_FILE)
    
    # Cek duplikasi
    existing_q = [q["question"] for q in knowledge_base["questions"]]
    if question in existing_q:
        await ctx.send("Lacus-chan: Aku udah tau itu kok! Gak perlu diajarin lagi hehe.")
        return

    # Simpan data baru
    knowledge_base["questions"].append({"question": question, "answer": answer})
    save_knowledge_base(DATABASE_FILE, knowledge_base)

    await ctx.send(f"✅ **Berhasil Disimpan!**\nQ: {question}\nA: {answer}\nSekarang coba tanya lagi!")

# ======================================================
# COMMAND VOICE / MUSIC
# (Tidak ada perubahan)
# ======================================================

@bot.command()
async def join(ctx):
    if not ctx.author.voice:
        return await ctx.send(f'{ctx.author.name}, kamu belum join voice channel.')
    await ctx.author.voice.channel.connect()
    await ctx.send("Udah aku join yaa~ 💞")

@bot.command()
async def leave(ctx):
    if ctx.voice_client:
        await ctx.voice_client.disconnect()
        queues.pop(ctx.guild.id, None)
        await ctx.send("Aku udah keluar ya sayang~ 💔")
    else:
        await ctx.send("Aku gak ada di voice mana pun kok.")

@bot.command()
async def play(ctx, *, url):
    queue = get_queue(ctx)
    async with ctx.typing():
        try:
            players = await YTDLSource.from_url(url, loop=bot.loop)
            queue.extend(players)
            await ctx.send(f'Added to queue: {len(players)} tracks')

            if not ctx.voice_client.is_playing() and not ctx.voice_client.is_paused():
                await play_next(ctx)
        except Exception as e:
            await ctx.send(f'❌ Error: {e}')
            logging.error(e)

async def play_next(ctx):
    queue = get_queue(ctx)
    if queue:
        player = queue.pop(0)
        ctx.voice_client.play(player, after=lambda e: asyncio.run_coroutine_threadsafe(play_next(ctx), bot.loop))
        await ctx.send(f'🎵 Now playing: **{player.title}**')
    else:
        await asyncio.sleep(300)
        if not get_queue(ctx) and not ctx.voice_client.is_playing():
            await ctx.voice_client.disconnect()

# ======================================================
# EVENT ON_MESSAGE — RESPONSIVE PERSONALITY
# (Tidak ada perubahan)
# ======================================================

@bot.event
async def on_message(message):
    if message.author.bot:
        return

    msg = message.content.lower()
    if msg == "tell me the date":
        await message.channel.send(f"Today is {datetime.now().strftime('%A, %d %B %Y')}, darling!")
    elif msg == "sekarang hari apa":
        await message.channel.send(f"Sekarang hari {datetime.now().strftime('%A, %d %B %Y')}, sayang!")
    elif "morning" in msg:
        await message.channel.send(f"Morning darling, how's your sleep {message.author.mention}? ☀️")
    elif "goodnight" in msg:
        await message.channel.send(f"Goodnight darling, sleep well {message.author.mention} 😴")
    elif "darling" in msg:
        await message.channel.send(f"Y-Yes, Master {message.author.mention}? 💞")

    # AFK system
    if message.author.id in afk_users:
        afk_users.pop(message.author.id)
        await message.channel.send(f'Halooo {message.author.mention}, kamu udah balik yaa! 💖')

    if message.mentions:
        for user in message.mentions:
            if user.id in afk_users:
                await message.channel.send(f'{user.mention} lagi afk kak: {afk_users[user.id]}')

    await bot.process_commands(message)


# ======================================================
# SLASH COMMAND
# (Tidak ada perubahan)
# ======================================================

@bot.tree.command(name="hello", description="Hai dari Waifu Noufal Zaidaan 💖")
async def hello(interaction: discord.Interaction):
    await interaction.response.send_message(f"Hai {interaction.user.mention}! 💞 Aku Waifu Noufal Zaidaan siap menemanimu~")

@bot.tree.command(name="ping", description="Tes koneksi bot!")
async def slash_ping(interaction: discord.Interaction):
    await interaction.response.send_message("🏓 Pong! Aku aktif kok sayang~")


# ======================================================
# INTEGRASI AUTO VOICE SYSTEM
# (Tidak ada perubahan)
# ======================================================

setup_auto_voice_events(bot)


# ======================================================
# RUN BOT
# (Tidak ada perubahan)
# ======================================

try:
    bot.run(config.BOT_TOKEN)
except discord.errors.LoginFailure:
    print("❌ [FATAL ERROR] Token bot tidak valid. Periksa file config.py Anda.")
except discord.errors.PrivilegedIntentsRequired:
    print("❌ [FATAL ERROR] Intents tidak diaktifkan di Discord Developer Portal.")
    print("     -> Aktifkan 'PRESENCE INTENT', 'SERVER MEMBERS INTENT', dan 'MESSAGE CONTENT INTENT'.")