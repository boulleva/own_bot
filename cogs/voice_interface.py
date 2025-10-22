import discord
from discord.ui import View, Button, Modal, TextInput
from datetime import datetime
from zoneinfo import ZoneInfo 


WIB = ZoneInfo("Asia/Jakarta")  


class RenameModal(Modal, title="Ubah Nama Voice"):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel
        self.new_name = TextInput(
            label="Nama Baru",
            placeholder="Masukkan nama baru untuk voice channel...",
            max_length=50,
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.edit(name=self.new_name.value)
        await interaction.response.send_message(
            f"✅ Nama voice diubah menjadi **{self.new_name.value}**!", ephemeral=True
        )


class VoiceInterface(View):
    def __init__(self, owner: discord.Member, channel: discord.VoiceChannel):
        super().__init__(timeout=None)
        self.owner = owner
        self.channel = channel

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message("❌ Hanya pemilik voice yang bisa mengatur ini.", ephemeral=True)
            return False
        return True

    # === Buttons ===
    @discord.ui.button(label="Nama", style=discord.ButtonStyle.primary, emoji="📝", row=0)
    async def rename(self, interaction: discord.Interaction, button: Button):
        await interaction.response.send_modal(RenameModal(self.channel))

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.danger, emoji="🔒", row=0)
    async def lock(self, interaction: discord.Interaction, button: Button):
        await self.channel.set_permissions(self.channel.guild.default_role, connect=False)
        await interaction.response.send_message("🔒 Voice channel dikunci!", ephemeral=True)

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.success, emoji="🔓", row=0)
    async def unlock(self, interaction: discord.Interaction, button: Button):
        await self.channel.set_permissions(self.channel.guild.default_role, connect=True)
        await interaction.response.send_message("🔓 Voice channel dibuka!", ephemeral=True)

    @discord.ui.button(label="Limit +1", style=discord.ButtonStyle.secondary, emoji="👥", row=1)
    async def add_limit(self, interaction: discord.Interaction, button: Button):
        current_limit = self.channel.user_limit or 0
        new_limit = min(current_limit + 1, 99)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(f"👥 Limit dinaikkan menjadi **{new_limit}**.", ephemeral=True)

    @discord.ui.button(label="Hapus", style=discord.ButtonStyle.danger, emoji="🗑️", row=1)
    async def delete(self, interaction: discord.Interaction, button: Button):
        await self.channel.delete()
        await interaction.response.send_message("🗑️ Voice channel telah dihapus.", ephemeral=True)


async def send_voice_interface(channel: discord.TextChannel, owner: discord.Member, voice: discord.VoiceChannel):
    """Kirim embed interface kontrol voice"""
    # embed = discord.Embed(
    #     title="Lacus Clyne Voice 💖",
    #     description=(
    #         f"**Interface** ini dapat digunakan untuk mengatur **voice sementara** kamu.\n"
    #         f"Opsi lainnya tersedia melalui perintah `/voice`.\n\n"
    #         f"🔹 Pemilik: {owner.mention}\n"
    #         f"🔹 Channel: `{voice.name}`"
    #     ),
    #     color=discord.Color.blurple(),
    #     timestamp=datetime.utcnow()
    # )
    # embed.set_author(name="TempVoice Interface")
    # embed.set_footer(text="Gunakan tombol di bawah untuk mengatur voice channel kamu.")

    # view = VoiceInterface(owner=owner, channel=voice)
    # await channel.send(embed=embed, view=view)
