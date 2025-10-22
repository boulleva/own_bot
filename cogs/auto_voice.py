# cogs/auto_voice.py
import discord
from discord.ext import commands
from datetime import datetime
from zoneinfo import ZoneInfo
from .voice_button import VoiceControlView

AUTO_VC_CHANNEL_ID = 1430430889111982130  # ID "Join to Create"
LOG_CHANNEL_NAME = "log-voice"
WIB = ZoneInfo("Asia/Jakarta")

temporary_channels = {}

def setup_auto_voice_events(bot: commands.Bot):
    @bot.event
    async def on_voice_state_update(member, before, after):
        """Event utama untuk sistem Join to Create Voice"""
        if member.bot:
            return

        guild = member.guild
        log_channel = discord.utils.get(guild.text_channels, name=LOG_CHANNEL_NAME)

        # === 1. User masuk ke channel trigger ===
        if after.channel and after.channel.id == AUTO_VC_CHANNEL_ID:
            category = after.channel.category
            new_channel = await guild.create_voice_channel(
                name=f"🔊 {member.display_name}'s Room",
                category=category
            )
            temporary_channels[new_channel.id] = member.id
            await member.move_to(new_channel)

            # Embed log creation
            if log_channel:
                embed = discord.Embed(
                    title="🎧 Voice Channel Dibuat",
                    description=f"{member.mention} membuat channel: `{new_channel.name}`",
                    color=discord.Color.green(),
                    timestamp=datetime.now(WIB)
                )
                embed.add_field(name="1430432299555623044", value=str(new_channel.id))
                embed.set_author(name=member.display_name, icon_url=member.display_avatar.url)
                embed.set_footer(text=f"Guild: {guild.name}")

                # Tombol kontrol voice
                view = VoiceControlView(owner=member, channel=new_channel)
                await log_channel.send(embed=embed, view=view)

        # === 2. Channel kosong → hapus ===
        if before.channel and before.channel.id in temporary_channels:
            try:
                channel_to_check = bot.get_channel(before.channel.id) or await bot.fetch_channel(before.channel.id)
                if channel_to_check and len(channel_to_check.members) == 0:
                    owner_id = temporary_channels[before.channel.id]
                    owner = guild.get_member(owner_id)

                    await channel_to_check.delete(reason="Channel temporer kosong")
                    del temporary_channels[before.channel.id]

                    if log_channel:
                        embed = discord.Embed(
                            title="🗑️ Voice Channel Dihapus",
                            description=f"Channel `{before.channel.name}` milik {owner.mention if owner else 'Unknown'} dihapus.",
                            color=discord.Color.red(),
                            timestamp=datetime.now(WIB)
                        )
                        await log_channel.send(embed=embed)

            except discord.NotFound:
                if before.channel.id in temporary_channels:
                    del temporary_channels[before.channel.id]
            except Exception as e:
                print(f"Error saat mengecek/menghapus channel: {e}")
                if before.channel.id in temporary_channels:
                    del temporary_channels[before.channel.id]
