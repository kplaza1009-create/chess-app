"""Run a reproducible position or a small perft tree from the command line."""

import argparse

from .engine import START_FEN, ChessError, Game, Position, divide, perft


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--fen", default=START_FEN)
    parser.add_argument("--moves", nargs="*", default=[])
    parser.add_argument("--perft", type=int, choices=range(0, 6), metavar="0..5")
    parser.add_argument("--divide", type=int, choices=range(1, 6), metavar="1..5")
    args = parser.parse_args()
    try:
        game = Game(Position.from_fen(args.fen))
        for move in args.moves:
            game.push(move)
        print(game.position.fen())
        print("Legal moves:", " ".join(m.uci() for m in game.position.legal_moves()))
        print("Check:", game.position.is_check())
        print("Outcome:", game.outcome())
        print("Claimable draws:", game.claimable_draws())
        if args.perft is not None:
            print("Perft:", perft(game.position, args.perft))
        if args.divide is not None:
            branches = divide(game.position, args.divide)
            for move, leaves in branches.items():
                print(f"{move}: {leaves}")
            print("Total:", sum(branches.values()))
    except ChessError as exc:
        parser.error(str(exc))


if __name__ == "__main__":
    main()
