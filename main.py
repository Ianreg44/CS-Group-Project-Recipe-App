"""CLI entry point for the fridge inventory and recipe suggester.

Run interactively:   python main.py
Run a quick demo:    python main.py --demo

Optional rich output: if the `rich` package is installed, output is colorized.
Otherwise it falls back to plain text — no extra dependency required.
"""

from __future__ import annotations

import argparse
import sys
from datetime import date
from pathlib import Path

from inventory import Inventory, FridgeItem
from recipes import RecipeMatch, Suggestions, load_recipes, suggest

try:  # optional dependency
    from rich.console import Console
    from rich.table import Table

    _console: "Console | None" = Console()
except ImportError:  # pragma: no cover - rich is optional
    _console = None


DATA_DIR = Path(__file__).parent / "data"
FRIDGE_PATH = DATA_DIR / "fridge.json"
RECIPES_PATH = DATA_DIR / "recipes.json"


# --- output helpers ---------------------------------------------------------

def _print(msg: str = "", style: str | None = None) -> None:
    if _console is not None and style:
        _console.print(msg, style=style)
    else:
        print(msg)


def _print_inventory(inventory: Inventory) -> None:
    items = inventory.view()
    if not items:
        _print("Fridge is empty.", style="yellow")
        return

    today = date.today()
    if _console is not None:
        table = Table(title="Fridge Inventory")
        table.add_column("#", justify="right")
        table.add_column("Name")
        table.add_column("Quantity", justify="right")
        table.add_column("Unit")
        table.add_column("Expires")
        for idx, item in enumerate(items, start=1):
            exp = item.expiration_date or "-"
            row_style = None
            if item.is_expired(today):
                exp = f"{exp} (EXPIRED)"
                row_style = "red"
            elif item.is_expiring_soon(today):
                days = item.days_until_expiration(today)
                exp = f"{exp} ({days}d left)"
                row_style = "yellow"
            table.add_row(str(idx), item.name, str(item.quantity), item.unit, exp, style=row_style)
        _console.print(table)
        return

    print("\nFridge Inventory:")
    print(f"{'#':>3}  {'Name':<20} {'Qty':>8}  {'Unit':<8} {'Expires':<12}")
    print("-" * 60)
    for idx, item in enumerate(items, start=1):
        exp = item.expiration_date or "-"
        marker = ""
        if item.is_expired(today):
            marker = " (EXPIRED)"
        elif item.is_expiring_soon(today):
            marker = f" ({item.days_until_expiration(today)}d left)"
        print(f"{idx:>3}  {item.name:<20} {item.quantity:>8.2f}  {item.unit:<8} {exp}{marker}")


def _format_match_line(match: RecipeMatch) -> str:
    pct = match.match_percentage
    return (
        f"{match.recipe.name} ({match.recipe.category}, {match.recipe.prep_time} min, "
        f"serves {match.recipe.servings}) — {pct:.0f}% match "
        f"[{match.have_enough_count}/{match.total} ingredients]"
    )


def _print_match_detail(match: RecipeMatch) -> None:
    if match.missing:
        names = ", ".join(f"{i.quantity} {i.unit} {i.name}" for i in match.missing)
        _print(f"   missing: {names}", style="red")
    if match.insufficient:
        for status in match.insufficient:
            have = status.matched_item
            need = status.needed
            _print(
                f"   short on {need.name}: have {have.quantity} {have.unit}, "
                f"need {need.quantity} {need.unit}",
                style="yellow",
            )
    notes = [s.note for s in match.statuses if s.note]
    for note in notes:
        _print(f"   note: {note}", style="dim")


def _print_section(title: str, matches: list[RecipeMatch], show_detail: bool = True) -> None:
    if not matches:
        return
    _print(f"\n=== {title} ===", style="bold cyan")
    for match in matches:
        _print(_format_match_line(match))
        if show_detail and not match.can_make_now:
            _print_match_detail(match)


def _print_suggestions(suggestions: Suggestions) -> None:
    has_anything = any(
        [
            suggestions.can_make_now,
            suggestions.almost,
            suggestions.uses_most,
            suggestions.expiring_priority,
        ]
    )
    if not has_anything:
        _print("No matching recipes — add more ingredients to your fridge.", style="yellow")
        return

    _print_section("Recipes you can make right now", suggestions.can_make_now, show_detail=False)
    _print_section("1-2 ingredients away", suggestions.almost)
    _print_section("Uses the most of your ingredients", suggestions.uses_most)
    if suggestions.expiring_priority:
        _print_section(
            "Use these soon — recipes with items expiring within 3 days",
            suggestions.expiring_priority,
        )


# --- input helpers ----------------------------------------------------------

def _prompt(message: str, default: str | None = None) -> str:
    suffix = f" [{default}]" if default else ""
    response = input(f"{message}{suffix}: ").strip()
    return response or (default or "")


def _prompt_float(message: str, default: float | None = None) -> float:
    while True:
        text = _prompt(message, str(default) if default is not None else None)
        try:
            return float(text)
        except ValueError:
            _print("Please enter a number.", style="red")


def _prompt_optional_date(message: str) -> str | None:
    text = _prompt(f"{message} (YYYY-MM-DD, blank to skip)").strip()
    if not text:
        return None
    try:
        date.fromisoformat(text)
    except ValueError:
        _print("Invalid date — skipping.", style="red")
        return None
    return text


# --- menu actions -----------------------------------------------------------

def action_view(inventory: Inventory) -> None:
    _print_inventory(inventory)
    expiring = inventory.expiring_soon()
    if expiring:
        names = ", ".join(i.name for i in expiring)
        _print(f"\nExpiring within 3 days: {names}", style="yellow")


def action_add(inventory: Inventory) -> None:
    name = _prompt("Item name")
    if not name:
        _print("Cancelled.", style="yellow")
        return
    quantity = _prompt_float("Quantity", default=1)
    unit = _prompt("Unit", default="unit")
    expiration = _prompt_optional_date("Expiration date")
    item = inventory.add(name=name, quantity=quantity, unit=unit, expiration_date=expiration)
    _print(f"Added: {item.quantity} {item.unit} {item.name}.", style="green")


def action_remove(inventory: Inventory) -> None:
    name = _prompt("Item to remove")
    if inventory.remove(name):
        _print(f"Removed {name}.", style="green")
    else:
        _print(f"No item named '{name}' found.", style="red")


def action_update(inventory: Inventory) -> None:
    name = _prompt("Item to update")
    item = inventory.find(name)
    if item is None:
        _print(f"No item named '{name}' found.", style="red")
        return
    quantity = _prompt_float(f"New quantity ({item.unit})", default=item.quantity)
    inventory.update_quantity(name, quantity)
    _print(f"Updated {name} to {quantity} {item.unit}.", style="green")


def action_suggest(inventory: Inventory) -> None:
    if not inventory.view():
        _print("Add ingredients to your fridge first.", style="yellow")
        return
    recipes = load_recipes(RECIPES_PATH)
    suggestions = suggest(inventory, recipes)
    _print_suggestions(suggestions)


# --- demo flow --------------------------------------------------------------

def run_demo() -> None:
    """Seed the fridge with a sample set of items and print suggestions."""
    demo_path = DATA_DIR / "fridge_demo.json"
    if demo_path.exists():
        demo_path.unlink()
    inventory = Inventory.load(demo_path)

    today = date.today()
    soon = (today.replace(day=min(today.day + 2, 28))).isoformat()
    seed: list[tuple[str, float, str, str | None]] = [
        ("egg", 6, "unit", None),
        ("milk", 500, "ml", soon),
        ("bread", 6, "slice", None),
        ("cheese", 200, "g", None),
        ("butter", 100, "g", None),
        ("tomato", 4, "unit", None),
    ]
    for name, qty, unit, exp in seed:
        inventory.add(name, qty, unit, exp)

    _print("Demo fridge stocked with:", style="bold")
    _print_inventory(inventory)

    recipes = load_recipes(RECIPES_PATH)
    _print("\nLoaded {} recipes.\n".format(len(recipes)), style="bold")
    _print_suggestions(suggest(inventory, recipes))

    # Clean up the demo file so we don't leave it behind.
    if demo_path.exists():
        demo_path.unlink()


# --- main loop --------------------------------------------------------------

MENU = """
========== Fridge App ==========
  1. View inventory
  2. Add item
  3. Remove item
  4. Update quantity
  5. Suggest recipes
  6. Quit
================================
"""


def main_menu() -> None:
    inventory = Inventory.load(FRIDGE_PATH)
    while True:
        _print(MENU, style="bold")
        choice = _prompt("Choose an option")
        if choice == "1":
            action_view(inventory)
        elif choice == "2":
            action_add(inventory)
        elif choice == "3":
            action_remove(inventory)
        elif choice == "4":
            action_update(inventory)
        elif choice == "5":
            action_suggest(inventory)
        elif choice in {"6", "q", "quit", "exit"}:
            _print("Goodbye.", style="green")
            return
        else:
            _print("Unrecognized option.", style="red")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Fridge inventory and recipe suggester.")
    parser.add_argument(
        "--demo", action="store_true", help="Run a non-interactive demo with sample ingredients."
    )
    args = parser.parse_args(argv)

    if args.demo:
        run_demo()
        return 0

    try:
        main_menu()
    except (KeyboardInterrupt, EOFError):
        _print("\nGoodbye.", style="green")
    return 0


if __name__ == "__main__":
    sys.exit(main())
