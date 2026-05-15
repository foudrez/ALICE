import os
import io
import logging
import asyncio
import discord
from discord.ext import commands
from dotenv import load_dotenv
from core.event_bus import EventBus

# Load environment variables
load_dotenv(dotenv_path="config/.env")

class AliceDiscordBot(commands.Bot):
    def __init__(self, bus: EventBus):
        intents = discord.Intents.default()
        intents.message_content = True
        intents.voice_states = True
        super().__init__(command_prefix="!", intents=intents)
        
        self.bus = bus
        self.voice_client = None
        
        # Subscribe to ALICE's internal events
        self.bus.subscribe("AUDIO_READY_TO_PLAY", self._on_audio_ready)
        self.bus.subscribe("LLM_TOKEN_GENERATED", self._on_typing_indicator)

    async def setup_hook(self):
        logging.info("[Discord] Bot is logging in...")

    async def on_ready(self):
        logging.info(f"[Discord] ALICE is online as {self.user}!")
        await self.change_presence(activity=discord.Game(name="osu! or Minecraft"))

    async def on_message(self, message):
        # Ignore her own messages
        if message.author == self.user:
            return

        # If someone mentions ALICE or replies to her
        if self.user in message.mentions or "alice" in message.content.lower():
            logging.info(f"[Discord] Message from {message.author}: {message.content}")
            
            # Format the message for her memory
            formatted_msg = f"{message.author.name} says: {message.content}"
            
            # Trigger her Brain
            await self.bus.publish("USER_SPOKE", formatted_msg)

        await self.process_commands(message)

    @commands.command(name="join")
    async def join_vc(self, ctx):
        """Commands ALICE to join the voice channel."""
        if ctx.author.voice:
            channel = ctx.author.voice.channel
            self.voice_client = await channel.connect()
            await ctx.send(f"Joined {channel.name}! I'm listening.")
            logging.info("[Discord] Joined Voice Channel.")
        else:
            await ctx.send("You need to be in a voice channel first!")

    @commands.command(name="leave")
    async def leave_vc(self, ctx):
        """Commands ALICE to leave the voice channel."""
        if self.voice_client:
            await self.voice_client.disconnect()
            self.voice_client = None
            await ctx.send("Leaving voice channel.")

    async def _on_typing_indicator(self, token: str):
        """Optional: Could be used to trigger Discord's typing indicator."""
        pass 

    async def _on_audio_ready(self, audio_bytes: bytes):
        """When the TTS engine generates voice, play it in the Discord VC."""
        if self.voice_client and self.voice_client.is_connected():
            logging.info("[Discord] Streaming voice to Discord VC...")
            
            # Convert raw bytes to a file-like object Discord can play
            audio_stream = io.BytesIO(audio_bytes)
            source = discord.PCMAudio(audio_stream)
            
            # Play the audio (if not already playing something)
            if not self.voice_client.is_playing():
                self.voice_client.play(source, after=lambda e: print('Player error: %s' % e) if e else None)
        else:
            # If not in a VC, you could theoretically have her send a text reply here instead.
            pass

    async def start_bot(self):
        token = os.getenv("DISCORD_TOKEN")
        if not token:
            logging.error("[Discord] Missing DISCORD_TOKEN in config/.env")
            return
        await self.start(token)