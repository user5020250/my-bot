import random
import time
from datetime import datetime, timedelta, timezone

import discord
from discord import app_commands
from discord.ext import commands

from database import get_conn
import db_utils as db

WHITE = discord.Color(0xFFFFFF)

def parse_amount(amount: str) -> int:
    amount = amount.lower().replace(",", "").strip()

    multipliers = {
        "k": 1_000,
        "m": 1_000_000,
        "b": 1_000_000_000,
        "t": 1_000_000_000_000,
    }

    if amount == "all":
        return -1

    suffix = amount[-1]

    if suffix in multipliers:
        number = float(amount[:-1])
        return int(number * multipliers[suffix])

    return int(amount)

# ------------------------------------------------------------------ /loan

LOAN_INTEREST_RATE = 0.20
LOAN_DUE_DAYS = 7
LOAN_REQUEST_TIMEOUT_SECONDS = 60

# Every full LOAN_ESCALATION_INTERVAL_SECONDS a loan stays overdue,
# its remaining balance gets hit with another penalty, and that
# penalty rate itself grows each time it's applied. Escalation stops
# once LOAN_MAX_ESCALATIONS has been reached, so remaining balances
# can't blow up forever.
LOAN_ESCALATION_INTERVAL_SECONDS = 24 * 60 * 60  # once per day overdue
LOAN_ESCALATION_RATE_STEP = 0.05  # +5% penalty rate per escalation
LOAN_MAX_ESCALATIONS = 52  # hard cap so this can't run away


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
            created_at INTEGER NOT NULL,
            overdue_count INTEGER NOT NULL DEFAULT 0,
            last_escalated_at INTEGER
        )
        """
    )

    # Migrate databases created before the overdue-escalation columns
    # existed, so this doesn't break on existing installs.
    existing_cols = {
        row["name"] for row in conn.execute("PRAGMA table_info(loans)")
    }

    if "overdue_count" not in existing_cols:
        conn.execute(
            "ALTER TABLE loans ADD COLUMN overdue_count INTEGER NOT NULL DEFAULT 0"
        )

    if "last_escalated_at" not in existing_cols:
        conn.execute(
            "ALTER TABLE loans ADD COLUMN last_escalated_at INTEGER"
        )

    conn.commit()
    conn.close()


def is_overdue(loan) -> bool:
    """True if this loan is active and past its due date."""
    return loan["status"] == "active" and loan["due_date"] < int(time.time())


def current_penalty_rate(overdue_count: int) -> float:
    """The interest rate that would be applied on the next escalation."""
    return LOAN_INTEREST_RATE + overdue_count * LOAN_ESCALATION_RATE_STEP


def escalate_if_overdue(conn, loan):
    """
    If `loan` is active and past due, apply compounding interest for
    every full LOAN_ESCALATION_INTERVAL_SECONDS it's been overdue since
    the last escalation (or since the due date, if never escalated).

    Each escalation increases both the remaining balance AND the rate
    used for the *next* escalation, so interest keeps getting worse the
    longer someone avoids paying. Returns the (possibly updated) loan
    row, re-fetched from the DB if a change was made.
    """
    if loan["status"] != "active":
        return loan

    now = int(time.time())

    if now < loan["due_date"]:
        return loan

    overdue_count = loan["overdue_count"]

    if overdue_count >= LOAN_MAX_ESCALATIONS:
        return loan

    last_point = loan["last_escalated_at"] or loan["due_date"]
    periods = (now - last_point) // LOAN_ESCALATION_INTERVAL_SECONDS

    if periods <= 0:
        return loan

    periods = min(periods, LOAN_MAX_ESCALATIONS - overdue_count)

    remaining = loan["remaining"]

    for _ in range(periods):
        overdue_count += 1
        rate = current_penalty_rate(overdue_count - 1)
        remaining = round(remaining * (1 + rate))

    new_last_escalated_at = last_point + periods * LOAN_ESCALATION_INTERVAL_SECONDS

    conn.execute(
        """
        UPDATE loans
        SET remaining = ?,
            overdue_count = ?,
            last_escalated_at = ?
        WHERE id = ?
        """,
        (remaining, overdue_count, new_last_escalated_at, loan["id"]),
    )
    conn.commit()

    loan = conn.execute(
        "SELECT * FROM loans WHERE id = ?",
        (loan["id"],),
    ).fetchone()

    return loan


class LoanRequestView(discord.ui.View):
    """
    Confirmation buttons shown to the lender when a borrower
    sends a /loan request. Expires automatically after
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
            title="💸 Loan Request",
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
                        f"⌛ {self.borrower.mention}'s loan request to "
                        f"{self.lender.mention} has expired.",
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
                "🚫 This request isn't for you.",
                ephemeral=True,
            )
            return

        if self.resolved:
            await interaction.response.send_message(
                "🔒 This request has already been resolved.",
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
                    f"🚫 Not approved. {self.lender.mention} doesn't have "
                    f"enough money.",
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
                created_at,
                overdue_count,
                last_escalated_at
            )
            VALUES (?, ?, ?, ?, ?, 'active', ?, 0, NULL)
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
            title="✅ Loan Approved",
            description=(
                f"{self.lender.mention} lent "
                f"**{db.format_peso(self.principal)}** "
                f"to {self.borrower.mention}.\n\n"
                f"Total due: **{db.format_peso(self.total_due)}**\n"
                f"Due date: <t:{self.due_ts}:D>\n"
                f"Loan ID: `{loan_id}`\n\n"
                f"Use `/loan pay` to repay."
            ),
            color=WHITE,
        )

        embed.set_footer(
            text=f"💰 {self.borrower.display_name}'s balance: {db.format_peso(new_balance)}"
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
                "🚫 This request isn't for you.",
                ephemeral=True,
            )
            return

        if self.resolved:
            await interaction.response.send_message(
                "🔒 This request has already been resolved.",
                ephemeral=True,
            )
            return

        self.resolved = True
        self.cog.pending_requests.pop(self.request_id, None)

        for child in self.children:
            child.disabled = True

        await interaction.response.edit_message(
            embed=self._closed_embed(
                "❌ Loan request declined.",
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

    # ---------------------------------------------------------- /loan group

    utang_group = app_commands.Group(
        name="loan",
        description="💰 Loan system.",
    )

   # ------------------------------------------------------- /loan request

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
    amount: str,
):
    borrower = interaction.user
    borrower_id = str(borrower.id)
    lender_id = str(lender.id)

    if lender_id == borrower_id:
        await interaction.response.send_message(
            "🚫 You can't borrow from yourself.",
            ephemeral=True,
        )
        return

    if lender.bot:
        await interaction.response.send_message(
            "🤖 Bots don't lend money.",
            ephemeral=True,
        )
        return

    try:
        principal = db.parse_amount(amount)
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid amount.\n"
            "Examples: `1k`, `500k`, `2m`, `1b`, `1t`.",
            ephemeral=True,
        )
        return

    if principal <= 0:
        await interaction.response.send_message(
            "❌ Amount must be greater than 0.",
            ephemeral=True,
        )
        return

    conn = get_conn()

    active_loans = conn.execute(
        """
        SELECT *
        FROM loans
        WHERE borrower = ?
        AND status = 'active'
        """,
        (borrower_id,),
    ).fetchall()

    overdue_loans = []

    for loan_row in active_loans:
        loan_row = escalate_if_overdue(conn, loan_row)

        if is_overdue(loan_row):
            overdue_loans.append(loan_row)

    conn.close()

    if overdue_loans:
        lines = [
            (
                f"`{loan['id']}`: "
                f"**{db.format_peso(loan['remaining'])}** "
                f"owed to <@{loan['lender']}> "
                f"— overdue <t:{loan['due_date']}:R>\n"
                f"Escalated: {loan['overdue_count']}x "
                f"({current_penalty_rate(loan['overdue_count']) * 100:.0f}% penalty)"
            )
            for loan in overdue_loans
        ]

        await interaction.response.send_message(
            "🚫 You still have overdue loans:\n\n"
            + "\n\n".join(lines)
            + "\n\nPay them first using `/loan pay`.",
            ephemeral=True,
        )
        return

    total_due = round(
        principal * (1 + LOAN_INTEREST_RATE)
    )

    due_dt = (
        datetime.now(timezone.utc)
        + timedelta(days=LOAN_DUE_DAYS)
    )

    due_ts = int(
        due_dt.timestamp()
    )

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
        color=WHITE,
        description=(
            f"👤 Borrower: {borrower.mention}\n"
            f"💰 Amount: **{db.format_peso(principal)}**\n"
            f"📈 Repayment: **{db.format_peso(total_due)}** "
            f"({int(LOAN_INTEREST_RATE * 100)}% interest)\n"
            f"📅 Due: <t:{due_ts}:D>"
        ),
    )

    embed.set_footer(
        text=(
            f"Request ID: {request_id} • "
            f"Expires in {LOAN_REQUEST_TIMEOUT_SECONDS} seconds"
        )
    )

    await interaction.response.send_message(
        content=lender.mention,
        embed=embed,
        view=view,
    )

    view.message = await interaction.original_response()

    self.pending_requests[request_id] = view

       # ------------------------------------------------------- /loan pay

@utang_group.command(
    name="pay",
    description="Pay a specific loan.",
)
@app_commands.describe(
    loan_id="The loan ID to pay",
    amount="How much to pay",
)
async def utang_pay(
    self,
    interaction: discord.Interaction,
    loan_id: int,
    amount: str,
):
    borrower_id = str(interaction.user.id)

    try:
        amount = db.parse_amount(amount)
    except ValueError:
        await interaction.response.send_message(
            "❌ Invalid amount.\n"
            "Examples: `1k`, `500k`, `2m`, `1b`, `1t`.",
            ephemeral=True,
        )
        return

    conn = get_conn()

    loan = conn.execute(
        """
        SELECT *
        FROM loans
        WHERE id = ?
        AND borrower = ?
        AND status = 'active'
        """,
        (
            loan_id,
            borrower_id,
        ),
    ).fetchone()

    if loan is None:
        conn.close()

        await interaction.response.send_message(
            f"❌ No active loan found with ID `{loan_id}`.",
            ephemeral=True,
        )
        return

    loan = escalate_if_overdue(conn, loan)

    borrower_user = db.get_user(
        borrower_id
    )

    pay_amount = min(
        amount,
        loan["remaining"],
        borrower_user["balance"],
    )

    if pay_amount <= 0:
        conn.close()

        await interaction.response.send_message(
            "💸 You don't have enough money.",
            ephemeral=True,
        )
        return

    new_remaining = loan["remaining"] - pay_amount

    if new_remaining <= 0:
        conn.execute(
            """
            UPDATE loans
            SET remaining = 0,
                status = 'paid'
            WHERE id = ?
            """,
            (loan_id,),
        )
    else:
        conn.execute(
            """
            UPDATE loans
            SET remaining = ?
            WHERE id = ?
            """,
            (
                new_remaining,
                loan_id,
            ),
        )

    conn.commit()
    conn.close()

    db.add_balance(
        borrower_id,
        -pay_amount,
    )

    db.add_balance(
        loan["lender"],
        pay_amount,
    )

    description = (
        f"🏦 Loan ID: `{loan_id}`\n"
        f"👤 Lender: <@{loan['lender']}>\n"
        f"💵 Paid: **{db.format_peso(pay_amount)}**\n"
        f"💰 Remaining: **{db.format_peso(new_remaining)}**"
    )

    if new_remaining <= 0:
        description += (
            "\n\n✅ This loan has been fully paid."
        )

    elif loan["overdue_count"] > 0:
        description += (
            f"\n\n⚠️ This loan has been escalated "
            f"{loan['overdue_count']}x due to late payment."
            "\nInterest will continue increasing until it is paid."
        )

    embed = discord.Embed(
        title="💵 Loan Payment",
        description=description,
        color=WHITE,
    )

    await interaction.response.send_message(
        embed=embed
    )
    # ---------------------------------------------------------- /loan list

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

        borrowed = [escalate_if_overdue(conn, loan) for loan in borrowed]
        lent = [escalate_if_overdue(conn, loan) for loan in lent]

        conn.close()

        embed = discord.Embed(
            title="📒 Loan Overview",
            color=WHITE,
        )

        if borrowed:
            lines = []

            for loan in borrowed:
                line = (
                    f"`{loan['id']}` To <@{loan['lender']}>: "
                    f"**{db.format_peso(loan['remaining'])}** "
                    f"(due <t:{loan['due_date']}:R>)"
                )

                if is_overdue(loan):
                    line += f" ⚠️ OVERDUE, escalated {loan['overdue_count']}x"

                lines.append(line)

            embed.add_field(
                name="📤 You owe",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="📤 You owe",
                value="Nothing.",
                inline=False,
            )

        if lent:
            lines = []

            for loan in lent:
                line = (
                    f"`{loan['id']}` From <@{loan['borrower']}>: "
                    f"**{db.format_peso(loan['remaining'])}** "
                    f"(due <t:{loan['due_date']}:R>)"
                )

                if is_overdue(loan):
                    line += f" ⚠️ OVERDUE, escalated {loan['overdue_count']}x"

                lines.append(line)

            embed.add_field(
                name="📥 Owed to you",
                value="\n".join(lines),
                inline=False,
            )
        else:
            embed.add_field(
                name="📥 Owed to you",
                value="Nothing.",
                inline=False,
            )

        await interaction.response.send_message(embed=embed)

    # ---------------------------------------------------------- /loan info

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

        if loan is not None:
            loan = escalate_if_overdue(conn, loan)

        conn.close()

        if loan is None:
            await interaction.response.send_message(
                f"❌ No loan found with ID `{loan_id}`."
            )
            return

        user_id = str(interaction.user.id)

        if user_id not in (loan["lender"], loan["borrower"]):
            await interaction.response.send_message(
                "🚫 You can't view this loan."
            )
            return

        description = (
            f"Lender: <@{loan['lender']}>\n"
            f"Borrower: <@{loan['borrower']}>\n"
            f"Principal: **{db.format_peso(loan['principal'])}**\n"
            f"Remaining: **{db.format_peso(loan['remaining'])}**\n"
            f"Due: <t:{loan['due_date']}:D>\n"
            f"Status: `{loan['status']}`"
        )

        if loan["overdue_count"] > 0:
            description += (
                f"\n\n⚠️ Escalated {loan['overdue_count']}x due to late payment."
            )

            if loan["status"] == "active":
                description += (
                    f"\nNext penalty rate: "
                    f"{current_penalty_rate(loan['overdue_count']) * 100:.0f}%"
                )

        embed = discord.Embed(
            title=f"📄 Loan #{loan['id']}",
            description=description,
            color=WHITE,
        )

        await interaction.response.send_message(embed=embed)

    # ------------------------------------------------------- /loan cancel

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
                f"❌ No pending request found with ID `{request_id}`."
            )
            return

        if view.borrower.id != interaction.user.id:
            await interaction.response.send_message(
                "🚫 That's not your request."
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
                        title="💸 Loan Request",
                        description=(
                            f"❌ {view.borrower.mention} cancelled "
                            f"their loan request."
                        ),
                        color=WHITE,
                    ),
                    view=view,
                )
            except discord.HTTPException:
                pass

        await interaction.response.send_message(
            f"✅ Cancelled request `{request_id}`."
        )

async def setup(bot: commands.Bot):
    await bot.add_cog(
        Social(bot)
    )
