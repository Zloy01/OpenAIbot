import disnake
import os
import openai
import logging
import asyncio
from disnake.ext import commands
from datetime import timedelta
from time import time

# Настройка логирования
logging.basicConfig(level = logging.INFO, format = "%(asctime)s [%(levelname)s]: %(message)s", handlers = [ logging.StreamHandler() ])
logger = logging.getLogger(__name__)

# Конфигурация ключей
def setupApiKeys():
    openai.api_key = os.getenv("OPENAI_API_KEY")
    discordToken = os.getenv("DISCORD_BOT_TOKEN")

    if not openai.api_key:
        logger.error("OPENAI_API_KEY not found in environment variables")
        raise ValueError("Missing OpenAI API key")
    if not discordToken:
        logger.error("DISCORD_BOT_TOKEN not found in environment variables")
        raise ValueError("Missing Discord bot token")
    return discordToken

# Конфигурация ролей
class Config:
    ROLES = {
        "ban": 0,          # ID роли для заблокированных
        "admin": 0,        # ID роли для админов
        "newbie": 0,       # ID роли для новичков
        "constant": 0,     # ID роли для постоянных
        "old": 0,          # ID роли для старых
        "eternalold": 0,   # ID роли для вечно старых
        "pseudoowner": 0   # ID роли для псевдовладельцев
    }

# Инициализация бота
bot = commands.Bot(command_prefix = "!", intents = disnake.Intents.all(), help_command = None)
start_time = time()

# Группы команд
askGroup = bot.slash_command_group("ask", "Ask different OpenAI models")
accessGroup = bot.slash_command_group("member", "Access management commands")
imageGroup = bot.slash_command_group("image", "Image processing commands")

# Вспомогательные функции
def hasRole(member: disnake.Member, role_id: int) -> bool:
    return role_id in {role.id for role in member.roles}

def formatDuration(seconds: float) -> str:
    return str(timedelta(seconds=int(seconds)))

# События бота
@bot.event
async def on_ready():
    await bot.change_presence(status = disnake.Status.online, activity = disnake.Game("OpenAI Bot | /help"))
    logger.info(f"Bot {bot.user} is ready")

@bot.event
async def on_slash_command_error(inter: disnake.AppCmdInter, error: Exception):
    embed = disnake.Embed(color = disnake.Color.red())

    if isinstance(error, commands.CommandOnCooldown):
        embed.description = f"Cooldown: retry after {error.retry_after:.2f}s"
    elif isinstance(error, commands.MissingPermissions):
        embed.description = "Insufficient permissions"
    else:
        logger.error(f"Unhandled error: {error}")
        raise error

    await inter.response.send_message(embed = embed, ephemeral = True)

# Команды управления доступом
@accessGroup.command(name = "block", description = "Block bot access for a user")
@commands.has_permissions(administrator = True)
async def blockMember(inter: disnake.AppCmdInter, member: disnake.Member):
    if not (inter.author, Config.ROLES["admin"]):
        return await inter.response.send_message("Insufficient permissions", ephemeral = True)

    await member.add_roles(inter.guild.get_role(Config.ROLES["ban"]))
    await inter.response.send_message(f"{member.mention} ({member.name}) blocked", ephemeral = True)
    logger.info(f"{inter.author} blocked {member}")

@accessGroup.command(name = "unblock", description = "Unblock bot access for a user")
@commands.has_permissions(administrator=True)
async def unblockMember(inter: disnake.AppCmdInter, member: disnake.Member):
    if not (inter.author, Config.ROLES["admin"]):
        return await inter.response.send_message("Insufficient permissions", ephemeral = True)

    banRole = inter.guild.get_role(Config.ROLES["ban"])
    if banRole in member.roles:
        await member.remove_roles(banRole)
        await inter.response.send_message(f"{member.mention} ({member.name}) unblocked", ephemeral = True)
        logger.info(f"{inter.author} unblocked {member}")
    else:
        await inter.response.send_message(f"{member.mention} ({member.name}) is not blocked", ephemeral = True)

# Команды для GPT
@askGroup.command(name = "babbage", description = "Ask the Babbage model")
@commands.cooldown(1, 30, commands.BucketType.user)
async def ask_babbage(inter: disnake.AppCmdInter, prompt: str):
    if (inter.author, Config.ROLES["ban"]):
        return await inter.response.send_message("Bot access denied", ephemeral = True)

    await inter.response.defer()
    start = time()

    try:
        response = await asyncio.to_thread(
            openai.Completion.create,
            model = "text-babbage-001",
            prompt = prompt,
            temperature = 0.4,
            max_tokens = 1024,
            top_p = 0.1,
            frequency_penalty = 0.1,
            presence_penalty = 0.1
        )

        embed = disnake.Embed(description = f"Answer:\n{response.choices[0].text}", color = disnake.Color.blue())
        embed.add_field(name = "Prompt:", value = prompt, inline = False)
        embed.set_footer(text = f"Processed in {formatDuration(time() - start)}")

        await inter.followup.send(embed = embed)
        logger.info(f"{inter.author} asked Babbage: {prompt}")
    except Exception as e:
        await inter.followup.send(f"Error: {str(e)}", ephemeral=True)
        logger.error(f"Babbage error: {e}")

# Генерация изображений
@imageGroup.command(name = "generate", description = "Generate an image with DALL-E")
@commands.cooldown(1, 70, commands.BucketType.user)
async def generate_image(inter: disnake.AppCmdInter, prompt: str):
    if (inter.author, Config.ROLES["ban"]):
        return await inter.response.send_message("Bot access denied", ephemeral = True)

    await inter.response.defer()
    start = time()

    try:
        response = await asyncio.to_thread(openai.Image.create, prompt = prompt, n = 1, size = "1024x1024")

        embed = disnake.Embed(title = f"Generated image: {prompt}", color = disnake.Color.blue())
        embed.set_image(url = response.data[0].url)
        embed.set_footer(text = f"Processed in {formatDuration(time() - start)}")

        await inter.followup.send(embed = embed)
        logger.info(f"{inter.author} generated image: {prompt}")
    except Exception as e:
        await inter.followup.send(f"Error: {str(e)}", ephemeral = True)
        logger.error(f"DALL-E error: {e}")

# Запуск бота
def main():
    try:
        bot.run(setupApiKeys())
    except Exception as e:
        logger.error(f"Bot startup error: {e}")
        raise

if __name__ == "__main__":
    main()