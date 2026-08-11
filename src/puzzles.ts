import type { Puzzle } from './components/ChessBoard.vue'

// Hand-built placeholder seed data (see CLAUDE.md) — each solution line was
// verified legal (and mate/check where claimed) with chess.js before being
// added here. Real puzzle delivery will come from the Lichess CC0 database
// once the backend exists.
export const puzzles: Puzzle[] = [
  {
    // Black plays a harmless waiting move, then white finds the back-rank mate.
    fen: '6k1/1p3ppp/8/8/8/8/5PPP/R5K1 b - - 0 1',
    solution: ['b7b6', 'a1a8'],
  },
  {
    // Black plays a harmless waiting move, then white forks king and rook.
    fen: 'r3k3/ppp2ppp/8/1N6/8/8/PPP2PPP/4K3 b - - 0 1',
    solution: ['h7h6', 'b5c7'],
  },
  {
    // Scholar's mate: 1.e4 e5 2.Qh5 Nc6 3.Bc4 Nf6?? 4.Qxf7#
    fen: 'r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR b KQkq - 3 3',
    solution: ['g8f6', 'h5f7'],
  },
]
