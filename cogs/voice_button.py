# cogs/voice_button.py
import discord
from discord.ui import View, Button, Modal, TextInput

class VoiceControlView(View):
    def __init__(self, owner: discord.Member, channel: discord.VoiceChannel):
        super().__init__(timeout=None)
        self.owner = owner
        self.channel = channel  # <--- penting agar tombol tahu channel mana yang dikontrol

    async def interaction_check(self, interaction: discord.Interaction) -> bool:
        if interaction.user.id != self.owner.id:
            await interaction.response.send_message(
                "❌ Kamu bukan pemilik channel ini.", ephemeral=True
            )
            return False
        return True

    @discord.ui.button(label="Rename", style=discord.ButtonStyle.primary, emoji="📝")
    async def rename_button(self, interaction: discord.Interaction, button: Button):
        modal = RenameModal(self.channel)
        await interaction.response.send_modal(modal)

    @discord.ui.button(label="Lock", style=discord.ButtonStyle.danger, emoji="🔒")
    async def lock_button(self, interaction: discord.Interaction, button: Button):
        await self.channel.set_permissions(
            self.channel.guild.default_role, connect=False
        )
        await interaction.response.send_message(
            f"🔒 Channel **{self.channel.name}** telah dikunci!", ephemeral=True
        )

    @discord.ui.button(label="Unlock", style=discord.ButtonStyle.success, emoji="🔓")
    async def unlock_button(self, interaction: discord.Interaction, button: Button):
        await self.channel.set_permissions(
            self.channel.guild.default_role, connect=True
        )
        await interaction.response.send_message(
            f"🔓 Channel **{self.channel.name}** telah dibuka!", ephemeral=True
        )

    @discord.ui.button(label="Add Limit", style=discord.ButtonStyle.secondary, emoji="➕")
    async def add_limit_button(self, interaction: discord.Interaction, button: Button):
        current_limit = self.channel.user_limit or 0
        new_limit = min(current_limit + 1, 99)
        await self.channel.edit(user_limit=new_limit)
        await interaction.response.send_message(
            f"👥 Limit dinaikkan menjadi **{new_limit}**!", ephemeral=True
        )


class RenameModal(Modal, title="Rename Voice Channel"):
    def __init__(self, channel: discord.VoiceChannel):
        super().__init__()
        self.channel = channel

        self.new_name = TextInput(
            label="Nama Baru",
            placeholder="Masukkan nama baru untuk voice kamu...",
            max_length=50,
        )
        self.add_item(self.new_name)

    async def on_submit(self, interaction: discord.Interaction):
        await self.channel.edit(name=self.new_name.value)
        await interaction.response.send_message(
            f"✅ Nama voice diubah menjadi **{self.new_name.value}**!", ephemeral=True
        )
