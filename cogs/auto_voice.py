import discord
from discord.ext import commands
from datetime import datetime
from zoneinfo import ZoneInfo
from typing import List # <-- BARU: Diperlukan untuk type hinting

# ======================================================
# KONFIGURASI DASAR
# ======================================================

AUTO_VC_CHANNEL_ID = 1430430889111982130  # channel join to create
LOG_CHANNEL_NAME = "log-voice"
EDIT_CHANNEL_NAME = "edit-voice"  # interface permanen
WIB = ZoneInfo("Asia/Jakarta")

temporary_channels = {}
interface_message_id = None

# ======================================================
# FUNGSI: MEMBUAT INTERFACE PERMANEN
# ======================================================

# BUKAN LAGI EVENT. Ini adalah fungsi async biasa.
# Kita akan memanggil ini dari on_ready utama di main.py
async def setup_persistent_interface(bot: commands.Bot):
    """Menampilkan interface permanen di #edit-voice"""
    global interface_message_id
    
    # Menggunakan bot.wait_until_ready() jauh lebih aman daripada asyncio.sleep(3)
    await bot.wait_until_ready()
    print("[INFO] Cache bot siap, mencoba membuat interface...")

    edit_channel = discord.utils.get(bot.get_all_channels(), name=EDIT_CHANNEL_NAME)
    if not edit_channel:
        print(f"❌ [ERROR] Channel #{EDIT_CHANNEL_NAME} tidak ditemukan. Interface GAGAL.")
        return

    # --- DESKRIPSI EMBED DIMODIFIKASI ---
    embed = discord.Embed(
        title="🎛️ Voice Channel Control Panel",
        description=(
            "Gunakan tombol di bawah untuk mengelola voice channel kamu.\n\n"
            "📝 **Rename** – Ubah nama voice kamu\n"
            "🔒 **Lock** – Kunci agar orang lain tidak bisa join\n"
            "🔓 **Unlock** – Buka akses ke semua orang\n"
            "👥 **Set Limit** – Atur batas user (0-99)\n"
            "👢 **Kick** – Keluarkan user dari voice kamu\n\n"
            "👻 **Hide** – Sembunyikan channel dari daftar\n"
            "👁️ **Unhide** – Tampilkan channel ke publik\n"
            "🤝 **Permit** – Izinkan user tertentu melihat channel (saat hidden)\n"
            "🚫 **Revoke** – Cabut izin user melihat channel\n\n"
            "> Kamu harus menjadi **pemilik voice channel** untuk bisa menggunakannya."
        ),
        color=discord.Color.blurple(),
        timestamp=datetime.now(WIB),
    )
    embed.set_footer(text="Voice Manager aktif selama bot menyala.")

    # Pastikan view ini didaftarkan di setup_hook() pada main.py
    view = VoiceControlViewGlobal(bot)

    try:
        # Hapus interface lama (jika ada)
        async for msg in edit_channel.history(limit=10):
            if msg.author == bot.user:
                await msg.delete()

        message = await edit_channel.send(embed=embed, view=view)
        interface_message_id = message.id
        print(f"✅ [INFO] Interface permanen aktif di #{EDIT_CHANNEL_NAME}")

    except Exception as e:
        print(f"❌ [ERROR] Gagal membuat interface permanen: {e}")
        print("     -> Pastikan bot punya izin 'Send Messages', 'Manage Messages', & 'Embed Links' di channel itu.")


# ======================================================
# FUNGSI: SETUP EVENT VOICE (on_voice_state_update)
# ======================================================

def setup_auto_voice_events(bot: commands.Bot):
    """
    Mendaftarkan semua event yang berhubungan dengan auto-voice
    (kecuali on_ready/interface)
    """

    # -----------------------------------------------
    # EVENT: ON_VOICE_STATE_UPDATE — buat / hapus VC
    # -----------------------------------------------
    @bot.event
    async def on_voice_state_update(member, before, after):
        if member.bot:
            return

        guild = member.guild
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

        # ======= Membuat voice channel baru =======
        if after.channel and after.channel.id == AUTO_VC_CHANNEL_ID:
            category = after.channel.category
            try:
                # --- DIMODIFIKASI: Atur izin awal saat membuat channel ---
                # Default: @everyone bisa melihat, tapi tidak bisa join (jika owner mau)
                # Owner (member) BISA melihat dan connect.
                overwrites = {
                    guild.default_role: discord.PermissionOverwrite(view_channel=True),
                    member: discord.PermissionOverwrite(view_channel=True, connect=True, manage_channels=True)
                }
                
                new_channel = await guild.create_voice_channel(
                    name=f"🔊 {member.display_name}'s Kingdom",
                    category=category,
                    overwrites=overwrites # <-- Terapkan izin
                )
                # --------------------------------------------------------
                
                temporary_channels[new_channel.id] = member.id
                await member.move_to(new_channel)

                if log_channel:
                    embed = discord.Embed(
                        title="🎧 Voice Channel Dibuat",
                        description=f"{member.mention} membuat channel: `{new_channel.name}`",
                        color=discord.Color.green(),
                        timestamp=datetime.now(WIB),
                    )
                    embed.add_field(name="Channel ID", value=new_channel.id)
                    embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                    embed.set_footer(text=f"Guild: {guild.name}")
                    await log_channel.send(embed=embed)
            except Exception as e:
                print(f"❌ [ERROR] Gagal membuat VC baru: {e}")

        # ======= Menghapus voice channel kosong =======
        if before.channel and before.channel.id in temporary_channels:
            try:
                # Perlu re-fetch channel untuk data member yang update
                channel = bot.get_channel(before.channel.id) 
                
                # Cek jika channel masih ada DAN jumlah membernya 0
                if channel and len(channel.members) == 0:
                    owner_id = temporary_channels.pop(before.channel.id, None)
                    await channel.delete(reason="Channel temporer kosong")

                    if log_channel:
                        owner = guild.get_member(owner_id) if owner_id else None
                        embed = discord.Embed(
                            title="🗑️ Voice Channel Dihapus",
                            description=f"Channel `{before.channel.name}` milik {owner.mention if owner else 'Unknown'} dihapus.",
                            color=discord.Color.red(),
                            timestamp=datetime.now(WIB),
                        )
                        await log_channel.send(embed=embed)
            except discord.NotFound:
                # Channel sudah terhapus, bersihkan dari memori
                temporary_channels.pop(before.channel.id, None)
            except Exception as e:
                print(f"❌ [ERROR] Gagal hapus channel: {e}")
                # Bersihkan dari memori jika terjadi error
                temporary_channels.pop(before.channel.id, None)


# ======================================================
# BARU: KICK SELECT (Dropdown)
# ======================================================

class KickSelect(discord.ui.Select):
    def __init__(self, channel: discord.VoiceChannel, owner: discord.Member):
        self.channel = channel
        
        # Buat daftar pilihan HANYA dari member di channel, KECUALI si owner
        options = [
            discord.SelectOption(label=member.display_name, value=str(member.id), emoji="👤")
            for member in channel.members if member.id != owner.id
        ]

        if not options:
            options.append(discord.SelectOption(label="Tidak ada orang untuk di-kick", value="disabled", emoji="🤷"))
            
        super().__init__(placeholder="Pilih user yang akan di-kick...", min_values=1, max_values=1, options=options)

    async def callback(self, interaction: discord.Interaction):
        if self.values[0] == "disabled":
            return await interaction.response.edit_message(content="❌ Tidak ada user yang bisa di-kick.", view=None)
            
        user_id = int(self.values[0])
        member = interaction.guild.get_member(user_id)
        
        if member and member in self.channel.members:
            try:
                await member.move_to(None, reason=f"Di-kick oleh owner channel ({interaction.user.name})")
                await interaction.response.edit_message(content=f"👢 **{member.display_name}** telah di-kick dari channel.", view=None)
            except discord.Forbidden:
                await interaction.response.edit_message(content=f"❌ Bot tidak punya izin untuk me-kick {member.display_name}.", view=None)
            except Exception as e:
                await interaction.response.edit_message(content=f"❌ Gagal me-kick user: {e}", view=None)
        else:
            await interaction.response.edit_message(content="❌ User tersebut sudah tidak ada di channel.", view=None)

# ======================================================
# BARU: PERMIT/REVOKE SELECT (User Select)
# ======================================================

class UserAccessSelect(discord.ui.UserSelect):
    def __init__(self, channel: discord.VoiceChannel, mode: str):
        self.channel = channel
        self.mode = mode # "permit" atau "revoke"
        
        placeholder = "Pilih user untuk diberi izin..." if mode == "permit" else "Pilih user untuk dicabut izinnya..."
        super().__init__(placeholder=placeholder, min_values=1, max_values=1)

    async def callback(self, interaction: discord.Interaction):
        member = self.values[0] # Ini adalah discord.Member object
        
        if self.mode == "permit":
            try:
                # Izinkan user untuk melihat DAN join
                await self.channel.set_permissions(member, view_channel=True, connect=True)
                await interaction.response.edit_message(content=f"🤝 **{member.display_name}** sekarang bisa melihat dan join channel.", view=None)
            except Exception as e:
                await interaction.response.edit_message(content=f"❌ Gagal memberi izin: {e}", view=None)
        
        elif self.mode == "revoke":
            try:
                # Kembalikan izin user ke default (None)
                await self.channel.set_permissions(member, view_channel=None, connect=None)
                await interaction.response.edit_message(content=f"🚫 Izin untuk **{member.display_name}** telah dicabut.", view=None)
            except Exception as e:
                await interaction.response.edit_message(content=f"❌ Gagal mencabut izin: {e}", view=None)


# ======================================================
# VIEW: Interface Permanen (DIMODIFIKASI)
# ======================================================

class VoiceControlViewGlobal(discord.ui.View):
    def __init__(self, bot: commands.Bot):
        super().__init__(timeout=None)  # Timeout=None membuatnya persisten
        self.bot = bot

    def get_user_channel(self, user: discord.Member):
        for vc_id, owner_id in temporary_channels.items():
            if owner_id == user.id:
                channel = self.bot.get_channel(vc_id)
                if channel: # Pastikan channel masih ada di cache
                    return channel
        return None

    # --- BARIS 1: Rename, Limit, Kick ---
    
    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, emoji="📝", custom_id="auto_voice:rename", row=0)
    async def rename_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        modal = RenameModalGlobal(channel)
        await interaction.response.send_modal(modal)

  # --- DIMODIFIKASI: Tombol Add Limit menjadi Set Limit ---
    @discord.ui.button(label="Set Limit", style=discord.ButtonStyle.secondary, emoji="👥", custom_id="auto_voice:set_limit", row=0)
    async def set_limit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        
        # Buka Modal (text box) baru
        modal = SetLimitModalGlobal(channel)
        await interaction.response.send_modal(modal)

    # --- BARU: Tombol Kick ---
    @discord.ui.button(label="Kick User", style=discord.ButtonStyle.danger, emoji="👢", custom_id="auto_voice:kick", row=0)
    async def kick_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        
        if len(channel.members) <= 1:
            return await interaction.response.send_message(
                "❌ Tidak ada user lain di channel kamu untuk di-kick.", ephemeral=True
            )

        # Buat View baru yang berisi KickSelect
        view = discord.ui.View(timeout=60)
        view.add_item(KickSelect(channel, interaction.user))
        await interaction.response.send_message("Pilih user yang ingin kamu kick:", view=view, ephemeral=True)

    # --- BARIS 2: Lock, Unlock ---

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.danger, emoji="🔒", custom_id="auto_voice:lock", row=1)
    async def lock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        try:
            # Mengunci = @everyone tidak bisa 'connect'
            await channel.set_permissions(channel.guild.default_role, connect=False)
            await interaction.response.send_message(
                f"🔒 Channel **{channel.name}** telah dikunci (user tidak bisa join)!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Gagal mengunci channel: {e}", ephemeral=True)

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.success, emoji="🔓", custom_id="auto_voice:unlock", row=1)
    async def unlock_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        try:
            # Membuka = @everyone bisa 'connect' (atau kembali ke default)
            await channel.set_permissions(channel.guild.default_role, connect=None)
            await interaction.response.send_message(
                f"🔓 Channel **{channel.name}** telah dibuka (user bisa join)!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Gagal membuka channel: {e}", ephemeral=True)

    # --- BARIS 3: Hide, Unhide ---

    # --- BARU: Tombol Hide ---
    @discord.ui.button(label="Hide", style=discord.ButtonStyle.danger, emoji="👻", custom_id="auto_voice:hide", row=2)
    async def hide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        try:
            # Menyembunyikan = @everyone tidak bisa 'view_channel'
            await channel.set_permissions(channel.guild.default_role, view_channel=False)
            await interaction.response.send_message(
                f"👻 Channel **{channel.name}** telah disembunyikan dari publik!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Gagal menyembunyikan channel: {e}", ephemeral=True)

    # --- BARU: Tombol Unhide ---
    @discord.ui.button(label="Unhide", style=discord.ButtonStyle.success, emoji="👁️", custom_id="auto_voice:unhide", row=2)
    async def unhide_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        try:
            # Membuka = @everyone bisa 'view_channel' (atau kembali ke default)
            await channel.set_permissions(channel.guild.default_role, view_channel=True)
            await interaction.response.send_message(
                f"👁️ Channel **{channel.name}** telah ditampilkan ke publik!", ephemeral=True
            )
        except Exception as e:
            await interaction.response.send_message(f"❌ Gagal menampilkan channel: {e}", ephemeral=True)

    # --- BARIS 4: Permit, Revoke ---

    # --- BARU: Tombol Permit ---
    @discord.ui.button(label="Permit User", style=discord.ButtonStyle.primary, emoji="🤝", custom_id="auto_voice:permit", row=3)
    async def permit_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )
        
        view = discord.ui.View(timeout=60)
        view.add_item(UserAccessSelect(channel, mode="permit"))
        await interaction.response.send_message("Pilih user yang ingin kamu beri izin:", view=view, ephemeral=True)

    # --- BARU: Tombol Revoke ---
    @discord.ui.button(label="Revoke User", style=discord.ButtonStyle.secondary, emoji="🚫", custom_id="auto_voice:revoke", row=3)
    async def revoke_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        channel = self.get_user_channel(interaction.user)
        if not channel:
            return await interaction.response.send_message(
                "❌ Kamu tidak memiliki voice channel aktif.", ephemeral=True
            )

        view = discord.ui.View(timeout=60)
        view.add_item(UserAccessSelect(channel, mode="revoke"))
        await interaction.response.send_message("Pilih user yang izinnya ingin kamu cabut:", view=view, ephemeral=True)


# ======================================================
# MODAL: Rename
# (Tidak ada perubahan)
# ======================================================

class RenameModalGlobal(discord.ui.Modal, title="Rename Voice Channel"):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel
        self.new_name = discord.ui.TextInput(
            label="Nama Baru", placeholder="Masukkan nama baru...", max_length=50
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        try:
            await self.channel.edit(name=self.new_name.value)
            await interaction.response.send_message(
                f"✅ Nama voice diubah menjadi **{self.new_name.value}**!", ephemeral=True
            )
        except Exception as e:
             await interaction.response.send_message(f"❌ Gagal mengubah nama: {e}", ephemeral=True)
             
# ======================================================
# BARU: MODAL: Set Limit
# ======================================================

class SetLimitModalGlobal(discord.ui.Modal, title="Set User Limit"):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel
        
        # Menampilkan limit saat ini sebagai nilai default di text box
        current_limit_str = str(channel.user_limit or 0)
        
        self.new_limit = discord.ui.TextInput(
            label="Batas User Baru (0 = Tanpa Batas)",
            placeholder="Masukkan angka antara 0 dan 99...",
            default=current_limit_str,
            max_length=2,
            style=discord.TextStyle.short,
            required=True
        )
        self.add_item(self.new_limit)

    async def on_submit(self, interaction: discord.Interaction):
        new_limit_str = self.new_limit.value.strip()
        
        # --- Validasi Input ---
        if not new_limit_str.isdigit():
            return await interaction.response.send_message(
                f"❌ Input tidak valid. Harap masukkan **angka** saja.", ephemeral=True
            )
            
        try:
            new_limit_int = int(new_limit_str)
        except ValueError:
            return await interaction.response.send_message(
                f"❌ Input tidak valid. Harap masukkan **angka** saja.", ephemeral=True
            )
        
        if not (0 <= new_limit_int <= 99):
            return await interaction.response.send_message(
                f"❌ Angka harus di antara **0** (tanpa batas) dan **99**.", ephemeral=True
            )
        # --- Akhir Validasi ---

        try:
            await self.channel.edit(user_limit=new_limit_int)
            
            if new_limit_int == 0:
                await interaction.response.send_message(
                    f"✅ Limit channel telah dihapus (tanpa batas)!", ephemeral=True
                )
            else:
                await interaction.response.send_message(
                    f"👥 Limit channel diatur menjadi **{new_limit_int}** user!", ephemeral=True
                )
        except Exception as e:
            await interaction.response.send_message(f"❌ Gagal mengubah limit: {e}", ephemeral=True)