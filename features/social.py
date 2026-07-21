import random
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

BUDOL_COOLDOWN_SECONDS = 24 * 60 * 60
KARAOKE_COOLDOWN_SECONDS = 5 * 60

BUDOL_SUCCESS_CHANCE = 0.4

# ------------------------------------------------------------------ /utang

LOAN_INTEREST_RATE = 0.20
LOAN_DUE_DAYS = 7
LOAN_REQUEST_TIMEOUT_SECONDS = 60


def ensure_loans_table():
    conn = get_conn()

    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS loans (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            lender TEXT NOT NULL,
            borrower TEXT NOT NULL,
            principal INTEGER NOT NULL,
            remaining INTEGER NOT NULL,
            due_date INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'active',
            created_at INTEGER NOT NULL
        )
        """
    )

    conn.commit()
    conn.close()


class LoanRequestView(discord.ui.View):
    """
    Confirmation buttons shown to the lender when a borrower
    sends a /utang request. Expires automatically after
    LOAN_REQUEST_TIMEOUT_SECONDS.
    """

    def __init__(
        self,
        cog: "Social",
        request_id: int,
        borrower: discord.Member,
        lender: discord.Member,
        principal: int,
        total_due: int,
        due_ts: int,
    ):
        super().__init__(timeout=LOAN_REQUEST_TIMEOUT_SECONDS)

        self.cog = cog
        self.request_id = request_id
        self.borrower = borrower
        self.lender = lender
        self.principal = principal
        self.total_due = total_due
        self.due_ts = due_ts
        self.message: discord.Message | None = None
        self.resolved = False

    def _closed_embed(self, description: str, color: discord.Color) -> discord.Embed:
        embed = discord.Embed(
            title="Loan Request",
            description=description,
            color=color,
        )
        return embed

    async def on_timeout(self):
        if self.resolved:
            return

        self.resolved = True
        self.cog.pending_requests.pop(self.request_id, None)

        for child in self.children:
            child.disabled = True

        if self.message is not None:
            try:
                await self.message.edit(
                    embed=self._closed_embed(
                        f"Nag-expire na ang loan request ni "
                        f"{self.borrower.mention} kay "
                        f"{self.lender.mention}.",
                        WHITE,
                    ),
                    view=self,
                )
            except discord.HTTPException:
                pass

    @discord.ui.button(
        label="Approve",
        style=discord.ButtonStyle.success,
        emoji="✅",
    )
    async def approve(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.lender.id:
            await interaction.response.send_message(
                "Hindi para sa'yo ang request na ito.",
                ephemeral=True,
            )
            return

        if self.resolved:
            await interaction.response.send_message(
                "Tapos na ang request na ito.",
                ephemeral=True,
            )
            return

        lender_user = db.get_user(str(self.lender.id))

        if lender_user["balance"] < self.principal:
            self.resolved = True
            self.cog.pending_requests.pop(self.request_id, None)

            for child in self.children:
                child.disabled = True

            await interaction.response.edit_message(
                embed=self._closed_embed(
                    f"Hindi na-approve. Wala nang sapat na pera si "
                    f"{self.lender.mention}.",
                    WHITE,
                ),
                view=self,
            )
            return

        self.resolved = True
        self.cog.pending_requests.pop(self.request_id, None)

        db.add_balance(str(self.lender.id), -self.principal)
        new_balance = db.add_balance(str(self.borrower.id), self.principal)

        conn = get_conn()

        cursor = conn.execute(
            """
            INSERT INTO loans (
                lender,
                borrower,
                principal,
                remaining,
                due_date,
                status,
                created_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?)
            """,
            (
                str(self.lender.id),
                str(self.borrower.id),
                self.principal,
                self.total_due,
                self.due_ts,
                int(time.time()),
            ),
        )

        loan_id = cursor.lastrowid

        conn.commit()
        conn.close()

        for child in self.children:
            child.disabled = True

        embed = discord.Embed(
            title="Loan Approved",
            description=(
                f"{self.lender.mention} lent "
                f"**{db.format_peso(self.principal)}** "
                f"to {self.borrower.mention}.\n\n"
                f"Total due: **{db.format_peso(self.total_due)}**\n"
                f"Due date: <t:{self.due_ts}:D>\n"
                f"Loan ID: `{loan_id}`\n\n"
                f"Use `/utang pay` to repay."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"{self.borrower.display_name}'s balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.edit_message(
            embed=embed,
            view=self,
        )

    @discord.ui.button(
        label="Decline",
        style=discord.ButtonStyle.danger,
        emoji="❌",
    )
    async def decline(
        self,
        interaction: discord.Interaction,
        button: discord.ui.Button,
    ):
        if interaction.user.id != self.lender.id:
            await interaction.response.send_message(
                "Hindi para sa'yo ang request na ito.",
                ephemeral=True,
            )
            return

        if self.resolved:
            await interaction.response.send_message(
                "Tapos na ang request na ito.",
                ephemeral=True,
            )
            return

        self.resolved = True
        self.cog.pending_requests.pop(self.request_id, None)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=self._closed_embed(
                "Loan request declined.",
                WHITE,
            ),
            view=self,
        )


class Social(commands.Cog):
    def __init__(self, bot: commands.Bot):
        self.bot = bot
        self.pending_requests: dict[int, LoanRequestView] = {}
        self._next_request_id = 1

        ensure_loans_table()

    # ---------------------------------------------------------- /utang group

    utang_group = app_commands.Group(
        name="utang",
        description="Loan system.",
    )

    # ------------------------------------------------------ /utang request

    @utang_group.command(
        name="request",
        description="Request a loan from another player.",
    )
    @app_commands.describe(
        lender="Who you're borrowing from",
        amount="How much to borrow",
    )
    async def utang_request(
        self,
        interaction: discord.Interaction,
        lender: discord.Member,
        amount: app_commands.Range[int, 1],
    ):
        borrower = interaction.user
        borrower_id = str(borrower.id)
        lender_id = str(lender.id)

        if lender_id == borrower_id:
            await interaction.response.send_message(
                "Hindi ka puwedeng umutang sa sarili mo."
            )
            return

        if lender.bot:
            await interaction.response.send_message(
                "Hindi nagpapautang ang bots."
            )
            return

        principal = int(amount)
        total_due = round(principal * (1 + LOAN_INTEREST_RATE))
        due_dt = datetime.now(timezone.utc) + timedelta(days=LOAN_DUE_DAYS)
        due_ts = int(due_dt.timestamp())

        request_id = self._next_request_id
        self._next_request_id += 1

        view = LoanRequestView(
            cog=self,
            request_id=request_id,
            borrower=borrower,
            lender=lender,
            principal=principal,
            total_due=total_due,
            due_ts=due_ts,
        )

        embed = discord.Embed(
            title="💸 Loan Request",
            description=(
                f"Borrower: {borrower.mention}\n"
                f"Amount: **{db.format_peso(principal)}**\n"
                f"Repayment: **{db.format_peso(total_due)}** "
                f"({int(LOAN_INTEREST_RATE * 100)}% interest)\n"
                f"Due: <t:{due_ts}:D>"
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Expires in {LOAN_REQUEST_TIMEOUT_SECONDS} seconds"
        )

        await interaction.response.send_message(
            content=lender.mention,
            embed=embed,
            view=view,
        )

        view.message = await interaction.original_response()
        self.pending_requests[request_id] = view

    # ----------------------------------------------------------- /utang pay

    @utang_group.command(
        name="pay",
        description="Pay off your active loans.",
    )
    @app_commands.describe(
        amount="How much to pay",
    )
    async def utang_pay(
        self,
        interaction: discord.Interaction,
        amount: app_commands.Range[int, 1],
    ):
        borrower_id = str(interaction.user.id)

        conn = get_conn()

        loans = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE borrower = ?
            AND status = 'active'
            ORDER BY created_at ASC
            """,
            (borrower_id,),
        ).fetchall()

        total_owed = sum(loan["remaining"] for loan in loans)

        if total_owed == 0:
            conn.close()

            await interaction.response.send_message(
                "Wala kang aktibong utang."
            )
            return

        borrower_user = db.get_user(borrower_id)

        pay_amount = min(
            amount,
            total_owed,
            borrower_user["balance"],
        )

        if pay_amount <= 0:
            conn.close()

            await interaction.response.send_message(
                "Wala kang sapat na pera."
            )
            return

        remaining_to_pay = pay_amount
        paid_lines = []

        for loan in loans:
            if remaining_to_pay <= 0:
                break

            payment = min(loan["remaining"], remaining_to_pay)
            new_remaining = loan["remaining"] - payment

            if new_remaining <= 0:
                conn.execute(
                    """
                    UPDATE loans
                    SET remaining = 0, status = 'paid'
                    WHERE id = ?
                    """,
                    (loan["id"],),
                )
            else:
                conn.execute(
                    """
                    UPDATE loans
                    SET remaining = ?
                    WHERE id = ?
                    """,
                    (new_remaining, loan["id"]),
                )

            db.add_balance(borrower_id, -payment)
            db.add_balance(loan["lender"], payment)

            paid_lines.append(
                f"Loan `{loan['id']}` → <@{loan['lender']}>: "
                f"**{db.format_peso(payment)}**"
            )

            remaining_to_pay -= payment

        conn.commit()
        conn.close()

        left = total_owed - pay_amount

        description = "\n".join(paid_lines)

        if left > 0:
            description += (
                f"\n\nMay natitira ka pang utang na "
                f"**{db.format_peso(left)}**."
            )
        else:
            description += "\n\nBayad na lahat ng utang mo."

        embed = discord.Embed(
            title="Bayad Utang",
            description=description,
            color=WHITE,
        )

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------- /utang list

    @utang_group.command(
        name="list",
        description="Show your active loans (as borrower and lender).",
    )
    async def utang_list(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(interaction.user.id)

        conn = get_conn()

        borrowed = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE borrower = ?
            AND status = 'active'
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()

        lent = conn.execute(
            """
            SELECT *
            FROM loans
            WHERE lender = ?
            AND status = 'active'
            ORDER BY created_at ASC
            """,
            (user_id,),
        ).fetchall()

        conn.close()

        embed = discord.Embed(
            title="Utang Overview",
            color=WHITE,
        )

        if borrowed:
            lines = [
                f"`{loan['id']}` To <@{loan['lender']}>: "
                f"**{db.format_peso(loan['remaining'])}** "
                f"(due <t:{loan['due_date']}:R>)"
                for loan in borrowed
            ]
            embed.add_field(
                name="You owe",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="You owe",
                value="Wala.",
                inline=False,
            )

        if lent:
            lines = [
                f"`{loan['id']}` From <@{loan['borrower']}>: "
                f"**{db.format_peso(loan['remaining'])}** "
                f"(due <t:{loan['due_date']}:R>)"
                for loan in lent
            ]
            embed.add_field(
                name="Owed to you",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="Owed to you",
                value="Wala.",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------- /utang info

    @utang_group.command(
        name="info",
        description="Show details for a specific loan.",
    )
    @app_commands.describe(
        loan_id="The loan ID",
    )
    async def utang_info(
        self,
        interaction: discord.Interaction,
        loan_id: int,
    ):
        conn = get_conn()

        loan = conn.execute(
            "SELECT * FROM loans WHERE id = ?",
            (loan_id,),
        ).fetchone()

        conn.close()

        if loan is None:
            await interaction.response.send_message(
                f"Walang loan na may ID `{loan_id}`."
            )
            return

        user_id = str(interaction.user.id)

        if user_id not in (loan["lender"], loan["borrower"]):
            await interaction.response.send_message(
                "Hindi mo makikita ang loan na ito."
            )
            return

        embed = discord.Embed(
            title=f"Loan #{loan['id']}",
            description=(
                f"Lender: <@{loan['lender']}>\n"
                f"Borrower: <@{loan['borrower']}>\n"
                f"Principal: **{db.format_peso(loan['principal'])}**\n"
                f"Remaining: **{db.format_peso(loan['remaining'])}**\n"
                f"Due: <t:{loan['due_date']}:D>\n"
                f"Status: `{loan['status']}`"
            ),
            color=WHITE,
        )

        await interaction.response.send_message(embed=embed)

    # -------------------------------------------------------- /utang cancel

    @utang_group.command(
        name="cancel",
        description="Cancel one of your pending loan requests.",
    )
    @app_commands.describe(
        request_id="The loan request ID",
    )
    async def utang_cancel(
        self,
        interaction: discord.Interaction,
        request_id: int,
    ):
        view = self.pending_requests.get(request_id)

        if view is None:
            await interaction.response.send_message(
                f"Walang pending request na may ID `{request_id}`."
            )
            return

        if view.borrower.id != interaction.user.id:
            await interaction.response.send_message(
                "Hindi mo request ito."
            )
            return

        view.resolved = True
        self.pending_requests.pop(request_id, None)

        for child in view.children:
            child.disabled = True

        if view.message is not None:
            try:
                await view.message.edit(
                    embed=discord.Embed(
                        title="Loan Request",
                        description=(
                            f"Kinansela ni {view.borrower.mention} "
                            f"ang loan request niya."
                        ),
                        color=WHITE,
                    ),
                    view=view,
                )
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            f"Kinansela ang request `{request_id}`."
        )

    # -------------------------------------------------------------- /budol

    @app_commands.command(
        name="budol",
        description="Try to scam another player.",
    )
    @app_commands.describe(
        target="Who to scam",
    )
    async def budol(
        self,
        interaction: discord.Interaction,
        target: discord.Member,
    ):
        scammer_id = str(
            interaction.user.id
        )

        target_id = str(
            target.id
        )

        if target_id == scammer_id:
            await interaction.response.send_message(
                "Hindi mo puwedeng i-budol ang sarili mo."
            )
            return

        if target.bot:
            await interaction.response.send_message(
                "Hindi naloloko ang bots."
            )
            return

        remaining = db.check_cooldown(
            scammer_id,
            "last_budol",
            BUDOL_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Mainit ka pa. "
                f"Try again in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            scammer_id,
            "last_budol",
            int(time.time()),
        )

        target_user = db.get_user(
            target_id
        )

        success = (
            random.random()
            < BUDOL_SUCCESS_CHANCE
        )

        if success:
            stolen = min(
                round(
                    target_user["balance"]
                    * random.uniform(
                        0.1,
                        0.3,
                    )
                ),
                5000,
            )

            if stolen <= 0:
                embed = discord.Embed(
                    title="Budol Attempt",
                    description=(
                        f"Wala ring pera si "
                        f"{target.mention}."
                    ),
                    color=WHITE,
                )

            else:
                db.add_balance(
                    target_id,
                    -stolen,
                )

                new_balance = db.add_balance(
                    scammer_id,
                    stolen,
                )

                embed = discord.Embed(
                    title="Budol Success",
                    description=(
                        f"Nakakuha ka ng "
                        f"**{db.format_peso(stolen)}** "
                        f"mula kay "
                        f"{target.mention}."
                    ),
                    color=WHITE,
                )

                embed.set_footer(
                    text=(
                        f"Balance: "
                        f"{db.format_peso(new_balance)}"
                    )
                )

        else:
            penalty = random.randint(
                100,
                1000,
            )

            new_balance = db.add_balance(
                scammer_id,
                -penalty,
            )

            embed = discord.Embed(
                title="Budol Failed",
                description=(
                    f"Nahuli ka ni "
                    f"{target.mention}.\n\n"
                    f"Multa: "
                    f"**{db.format_peso(penalty)}**."
                ),
                color=WHITE,
            )

            embed.set_footer(
                text=(
                    f"Balance: "
                    f"{db.format_peso(new_balance)}"
                )
            )

        await interaction.response.send_message(
            embed=embed
        )

    # ------------------------------------------------------------ /karaoke

    @app_commands.command(
        name="karaoke",
        description="Kumanta para kumita.",
    )
    async def karaoke(
        self,
        interaction: discord.Interaction,
    ):
        user_id = str(
            interaction.user.id
        )

        remaining = db.check_cooldown(
            user_id,
            "last_karaoke",
            KARAOKE_COOLDOWN_SECONDS,
        )

        if remaining > 0:
            await interaction.response.send_message(
                f"Nagpapahinga pa ang mic.\n"
                f"Try again in "
                f"**{db.format_duration(remaining)}**."
            )
            return

        db.set_cooldown(
            user_id,
            "last_karaoke",
            int(time.time()),
        )

        tip = random.randint(
            50,
            500,
        )

        new_balance = db.add_balance(
            user_id,
            tip,
        )

        songs = [
            "Narda",
            "Buwan",
            "Torete",
            "Beer",
            "Huling El Bimbo",
            "Pare Ko",
            "Uhaw",
            "With A Smile",
            "Kitchie Nadal Medley",
            "Harana",
        ]

        song = random.choice(
            songs
        )

        embed = discord.Embed(
            title="Videoke Time",
            description=(
                f"Kumanta ka ng "
                f"**{song}**.\n\n"
                f"Kumita ka ng "
                f"**{db.format_peso(tip)}**."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"Balance: {db.format_peso(new_balance)}"
        )

        await interaction.response.send_message(
            embed=embed
        )


async def setup(bot: commands.Bot):
    await bot.add_cog(
        Social(bot)
    )
