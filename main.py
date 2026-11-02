"""Launch Court Clash, the smooth local multiplayer basketball game."""

from court_clash import CourtClashGame


def main() -> None:
    game = CourtClashGame()
    game.run()


if __name__ == "__main__":
    main()

