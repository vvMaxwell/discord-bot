from __future__ import annotations

import random

import discord
from discord import app_commands
from discord.ext import commands


EIGHT_BALL_RESPONSES = [
    "Yes.",
    "No.",
    "Absolutely.",
    "Not a chance.",
    "Ask again after snacks.",
    "The vibes say yes.",
    "The vibes say no.",
    "Only if your friends agree.",
]

ROAST_LINES = [
    "{name} has the energy of a browser tab playing music somewhere and nobody can find it.",
    "{name} types like autocorrect is making business decisions.",
    "{name} could lose a hide and seek game in a studio apartment.",
    "{name} is proof that confidence and accuracy are distant cousins.",
]

COMPLIMENT_LINES = [
    "{name} is the kind of friend every group chat needs.",
    "{name} somehow makes chaos feel organized.",
    "{name} has elite main-character energy today.",
    "{name} could improve a room just by joining the voice call.",
]

TRUTHS = [
    "What is your most chaotic food opinion?",
    "What is the weirdest thing in your room right now?",
    "Which game would you brag about being good at, even if you are not?",
    "What is one message you typed and then wisely deleted?",
]

DARES = [
    "Talk in dramatic movie trailer voice for the next 2 minutes.",
    "Change your nickname to something chosen by the group for 10 minutes.",
    "Send the last photo in your camera roll to the chat if it is safe.",
    "Speak only in questions until your next turn.",
]

WOULD_YOU_RATHERS = [
    "Would you rather have free snacks forever or free games forever?",
    "Would you rather be overpowered in every co-op game or hilarious in every party game?",
    "Would you rather always win arguments or always win raffles?",
    "Would you rather have perfect aim or perfect luck?",
]


class Fun(commands.Cog):
    def __init__(self, bot: commands.Bot) -> None:
        self.bot = bot

    @app_commands.command(name="coinflip", description="Flip a coin.")
    async def coinflip(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(
            f"You flipped **{random.choice(['Heads', 'Tails'])}**."
        )

    @app_commands.command(name="roll", description="Roll one or more dice.")
    async def roll(
        self,
        interaction: discord.Interaction,
        sides: app_commands.Range[int, 2, 100] = 6,
        count: app_commands.Range[int, 1, 10] = 1,
    ) -> None:
        rolls = [random.randint(1, sides) for _ in range(count)]
        await interaction.response.send_message(
            f"Rolled `{count}d{sides}` -> **{', '.join(map(str, rolls))}** | Total: **{sum(rolls)}**"
        )

    @app_commands.command(name="choose", description="Choose between comma-separated options.")
    async def choose(self, interaction: discord.Interaction, options: str) -> None:
        choices = [option.strip() for option in options.split(",") if option.strip()]
        if len(choices) < 2:
            await interaction.response.send_message(
                "Give me at least two comma-separated options.",
                ephemeral=True,
            )
            return
        await interaction.response.send_message(f"I choose: **{random.choice(choices)}**")

    @app_commands.command(name="8ball", description="Ask the mystical 8-ball a question.")
    async def eight_ball(self, interaction: discord.Interaction, question: str) -> None:
        await interaction.response.send_message(
            f"Question: *{question}*\nAnswer: **{random.choice(EIGHT_BALL_RESPONSES)}**"
        )

    @app_commands.command(name="ship", description="Calculate friendship chemistry.")
    async def ship(
        self,
        interaction: discord.Interaction,
        first: discord.Member,
        second: discord.Member,
    ) -> None:
        seed = first.id + second.id
        random.seed(seed)
        score = random.randint(0, 100)
        random.seed()
        label = (
            "legendary duo"
            if score >= 85
            else "solid squad"
            if score >= 60
            else "chaotic experiment"
        )
        await interaction.response.send_message(
            f"**{first.display_name} + {second.display_name}** = **{score}%** compatibility, a {label}."
        )

    @app_commands.command(name="memeify", description="Turn text into mocking meme text.")
    async def memeify(self, interaction: discord.Interaction, text: str) -> None:
        transformed = "".join(
            character.upper() if index % 2 == 0 else character.lower()
            for index, character in enumerate(text)
        )
        await interaction.response.send_message(transformed)

    @app_commands.command(name="compliment", description="Give someone a nice boost.")
    async def compliment(
        self, interaction: discord.Interaction, member: discord.Member
    ) -> None:
        await interaction.response.send_message(
            random.choice(COMPLIMENT_LINES).format(name=member.mention)
        )

    @app_commands.command(name="roast", description="A lighthearted friendly roast.")
    async def roast(self, interaction: discord.Interaction, member: discord.Member) -> None:
        await interaction.response.send_message(
            random.choice(ROAST_LINES).format(name=member.mention)
        )

    @app_commands.command(name="rps", description="Play rock, paper, scissors.")
    @app_commands.choices(
        choice=[
            app_commands.Choice(name="Rock", value="rock"),
            app_commands.Choice(name="Paper", value="paper"),
            app_commands.Choice(name="Scissors", value="scissors"),
        ]
    )
    async def rps(
        self,
        interaction: discord.Interaction,
        choice: app_commands.Choice[str],
    ) -> None:
        bot_choice = random.choice(["rock", "paper", "scissors"])
        if bot_choice == choice.value:
            result = "It's a tie."
        elif (
            (choice.value == "rock" and bot_choice == "scissors")
            or (choice.value == "paper" and bot_choice == "rock")
            or (choice.value == "scissors" and bot_choice == "paper")
        ):
            result = "You win."
        else:
            result = "I win."
        await interaction.response.send_message(
            f"You picked **{choice.name}**. I picked **{bot_choice.title()}**. {result}"
        )

    @app_commands.command(name="truthordare", description="Get a random truth or dare.")
    @app_commands.choices(
        mode=[
            app_commands.Choice(name="Truth", value="truth"),
            app_commands.Choice(name="Dare", value="dare"),
            app_commands.Choice(name="Random", value="random"),
        ]
    )
    async def truth_or_dare(
        self,
        interaction: discord.Interaction,
        mode: app_commands.Choice[str],
    ) -> None:
        if mode.value == "truth":
            prompt = random.choice(TRUTHS)
            label = "Truth"
        elif mode.value == "dare":
            prompt = random.choice(DARES)
            label = "Dare"
        else:
            pool = [("Truth", random.choice(TRUTHS)), ("Dare", random.choice(DARES))]
            label, prompt = random.choice(pool)
        await interaction.response.send_message(f"**{label}:** {prompt}")

    @app_commands.command(
        name="wouldyourather",
        description="Get a random would-you-rather prompt.",
    )
    async def would_you_rather(self, interaction: discord.Interaction) -> None:
        await interaction.response.send_message(random.choice(WOULD_YOU_RATHERS))

    @app_commands.command(name="rate", description="Rate something out of 10.")
    async def rate(self, interaction: discord.Interaction, thing: str) -> None:
        score = random.randint(1, 10)
        await interaction.response.send_message(f"I rate **{thing}** a **{score}/10**.")


async def setup(bot: commands.Bot) -> None:
    await bot.add_cog(Fun(bot))
