import discord
from discord import app_commands
from discord.ext import commands


class Help(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot

    @app_commands.command(name="help", description="Show all commands and how to use them.")
    async def help(self, interaction: discord.Interaction):
        embed = discord.Embed(
            title="📖 Pinoy Economy Bot — Commands",
            description="Starting money: ₱1,000. Lahat ng halaga ay nasa pesos (₱).",
            color=discord.Color.teal(),
        )
        embed.add_field(
            name="/jobs",
            value="Tignan ang listahan ng trabaho at sahod.",
            inline=False,
        )
        embed.add_field(
            name="/trabaho job:<pumili>",
            value="Pumili o palitan ng trabaho. Gamitin ulit ang `/trabaho` (walang job) para kumita. 30 min cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/tambay",
            value="Mag-relax para sa maliit na swerte. 70% panalo, 30% may lugi. 1 min cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/sugal amount:<halaga>",
            value="Mag-bet sa 50/50 coinflip. Walang limit sa bet, walang cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/palengke presyo",
            value="Tignan ang presyo ngayon ng bigas, isda, mangga, manok, karne, at gulay.",
            inline=False,
        )
        embed.add_field(
            name="/palengke bili item:<pumili> quantity:<dami>",
            value="Bumili ng paninda sa palengke.",
            inline=False,
        )
        embed.add_field(
            name="/palengke benta item:<pumili> quantity:<dami>",
            value="Ibenta ang binili mong paninda.",
            inline=False,
        )
        embed.add_field(
            name="/load bili quantity:<dami>",
            value="Bumili ng load para ibenta ulit sa mas mataas na presyo.",
            inline=False,
        )
        embed.add_field(
            name="/load benta quantity:<dami>",
            value="Ibenta ang load mo. Random ang kita/lugi.",
            inline=False,
        )
        embed.add_field(
            name="/utang lender:<@user> amount:<halaga>",
            value="Manghiram ng pera sa ibang manlalaro. Walang cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/bayad lender:<@user> amount:<halaga>",
            value="Bayaran ang utang mo.",
            inline=False,
        )
        embed.add_field(
            name="/budol target:<@user>",
            value="Subukang manloko ng ibang manlalaro. Malaking kita kung successful, "
            "may parusa kung mahuli ka. 1 day cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/karaoke",
            value="Kumanta para sa tips (₱50-₱500). 5 min cooldown.",
            inline=False,
        )
        embed.add_field(
            name="/baon",
            value="I-claim ang araw-araw na baon (₱50-₱100). 24 hr cooldown.",
            inline=False,
        )
        embed.set_footer(text="Galing sa buhay Pinoy 🇵🇭 — gawa gamit ang discord.py")
        await interaction.response.send_message(embed=embed)


async def setup(bot: commands.Bot):
    await bot.add_cog(Help(bot))
