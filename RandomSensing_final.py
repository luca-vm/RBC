# Tumi Jourdan ~ 2180153
# Luca von Mayer ~ 2427051
# Mohammad Zaid Moonsamy ~ 2433079


import chess.engine
import random
import chess.engine
from reconchess import *
import reconchess.utilities as rutils
from collections import Counter
import sys

class RandomSensing(Player):

    def __init__(self):
        self.board = None
        self.color = None
        self.sense_counter = 0
        self.board_states = set()
        self.first_turn = True
        self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.board = board
        self.color = color
        self.board_states = {board.fen()}
        
    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):    
        
        if self.color and self.first_turn:
            self.first_turn = False
            return
        
        if captured_my_piece:
            self.board.remove_piece_at(capture_square) # for debugging purposes
            
            # Generate the possible board states after the opponent's capture move
            next_states = set()
            for state in self.board_states:
                
                
                board = chess.Board(state)
                #-----------
                board.turn = not self.color
                board.clear_stack()
                #-----------
                for move in self.generate_next_moves(board):
                    board_copy = chess.Board(state)
                    board_copy.turn = not self.color
                    if board_copy.is_capture(chess.Move.from_uci(move)):
                        board_copy.push(chess.Move.from_uci(move))
                        next_states.add(board_copy.fen())
                    
            self.board_states = next_states
            
        else:
            # If no capture occurred, generate the possible board states after the opponent's move
            next_states = set()
            for state in self.board_states:
                
                
                board = chess.Board(state)
                #-----------
                board.turn = not self.color
                board.clear_stack()
                #-----------
                for move in self.generate_next_moves(board):
                    board_copy = chess.Board(state)
                    board_copy.turn = not self.color
                    if not board_copy.is_capture(chess.Move.from_uci(move)):
                        board_copy.push(chess.Move.from_uci(move))
                        next_states.add(board_copy.fen())
                    
            self.board_states = next_states

    def choose_sense(self, sense_actions: List[Square], move_actions: List[chess.Move], seconds_left: float) -> Optional[Square]:
        # Filtering out the edge squares from the list of sense actions
        non_edge_squares = [square for square in sense_actions if square not in chess.SquareSet(chess.BB_RANK_1 | chess.BB_RANK_8 | chess.BB_FILE_A | chess.BB_FILE_H)]
        
        if non_edge_squares:
            return random.choice(non_edge_squares)
        else:
            return random.choice(sense_actions)
        
        
        
    def handle_sense_result(self, sense_result: List[Tuple[Square, Optional[chess.Piece]]]):
        # Debugging -> Update the self.board with the sensing result         
        self.board.turn = self.color
        self.board = rutils.without_opponent_pieces(self.board)   
        for square, piece in sense_result:
            self.board.set_piece_at(square, piece)

        # Filter out the inconsistent board states based on the sense result
        consistent_states = set()
        
        rejected_states = []
        
        for state in self.board_states:
            if self.is_consistent_with_window(state, sense_result):
                consistent_states.add(state)
            else:
                rejected_states.append(state)
        self.board_states = consistent_states
        
        if(len(self.board_states) == 0 ):
            self.board_states.add(self.board.fen())
            self.save_filtered_states(rejected_states)
            # sys.exit(0)



    def choose_move(self, move_actions: List[chess.Move], seconds_left: float) -> Optional[chess.Move]:
        if not move_actions:
            return None

        # Limit the number of board states to 10000
        if len(self.board_states) > 10000:
            self.board_states = set(random.sample(list(self.board_states), 10000))

        # Check if self.board_states is empty
        if not self.board_states:
            # If empty, choose a random move from move_actions
            return random.choice(move_actions)

        # Calculate the time limit for each board
        time_limit = 10 / (len(self.board_states))

        # Collect the moves suggested by Stockfish for each board state
        suggested_moves = []
      
        for state in self.board_states:
            board = chess.Board(state)
            capture_move = self.capture_opponent_king(board)
            if capture_move:
                suggested_moves.append(capture_move.uci())     
            else:
                
                board.turn = self.color
                # Check the validity of the board
                validity_check = board.status()
                if validity_check != chess.STATUS_VALID:
                    continue
    
                # Select the best move using Stockfish
                result = self.engine.play(board, chess.engine.Limit(time=time_limit))
                if (result.move):
                    suggested_moves.append(result.move.uci())
                else:
                    suggested_moves.append("0000")
       
        # Filter the suggested moves to only include valid moves from move_actions
        valid_moves = [move for move in suggested_moves if chess.Move.from_uci(move) in move_actions]
        # Count the occurrences of each valid move
        move_counts = Counter(valid_moves)

        # Select the most common valid move
        max_count = max(move_counts.values())
        most_common_moves = [move for move, count in move_counts.items() if count == max_count]
        voted_move = (most_common_moves)[0]

        # print("Voted move is ", voted_move)
        if voted_move and voted_move != "0000":
            return chess.Move.from_uci(voted_move)
        else:
            return None
        
    def handle_move_result(self, requested_move: Optional[chess.Move], taken_move: Optional[chess.Move],
                       captured_opponent_piece: bool, capture_square: Optional[Square]):
        
        statesBefore = self.board_states.copy()
         
        if taken_move and requested_move:
            if taken_move.uci() != requested_move.uci():
                temp_states = self.board_states.copy()
                for state in self.board_states:
                    board = chess.Board(state)
                    board.turn = self.color
                    if requested_move.uci() in self.generate_next_moves(board):
                        temp_states.remove(state)
                self.board_states = temp_states
                if(len(self.board_states) == 0 ):
                    self.board_states.add(self.board.fen())
                    # print("requested move lead to 0")
                    
        if taken_move is not None:
            # Update the board states based on the actual move that was taken
                self.board.turn = self.color
                self.board.push(taken_move)
                
                print(self.board)
                print(" ")
                
                self.board.turn = self.color
            
                updated_states = set()
                for state in self.board_states:
                    board = chess.Board(state)
                    board.turn = self.color
                    if taken_move.uci() in self.generate_next_moves(board):
                        board.push(taken_move)
                        board.turn = self.color
                        updated_states.add(board.fen())
                self.board_states = updated_states
                if(len(self.board_states) == 0 ):
                    self.board_states.add(self.board.fen())
                    # print("taken move lead to 0")
        
        
        if(len(self.board_states) == 0):
            self.board_states.add(self.board.fen())
            self.save_filtered_states(statesBefore)
            # print("Req Move : ", requested_move)
            # print("Tak Move : ", taken_move)
            # sys.exit(0)
  
                             

    def handle_game_end(self, winner_color: Optional[Color], win_reason: Optional[WinReason],
                        game_history: GameHistory):
        try:
            # if the engine is already terminated then this call will throw an exception
            self.engine.quit()
        except chess.engine.EngineTerminatedError:
            pass

    def generate_next_moves(self, board):
        next_moves = set()
        
        pseudolegal_moves = board.pseudo_legal_moves
        for move in pseudolegal_moves:
            next_moves.add(move.uci())

        next_moves.add(str(chess.Move.null()))

        for move in rutils.without_opponent_pieces(board).generate_castling_moves():
            if not rutils.is_illegal_castle(board, move):
                next_moves.add(move.uci())
        return (next_moves)
    
    def save_filtered_states(self,states):
        with open('filtered_board_states.txt', 'w') as file:
            for state in states:
                board = chess.Board(state)
                file.write(f"{board}\n")
                file.write("\n")
    
    def is_consistent_with_window(self, state_fen, window):
        board = chess.Board(state_fen)
        
        for observed_square,observed_piece in window:
            if (board.piece_at(observed_square) != observed_piece):
                return False
        return True
    
    def capture_opponent_king(self, board):
        enemy_king_square = board.king(not self.color)
        if enemy_king_square:
            # if there are any ally pieces that can take king, execute one of those moves
            enemy_king_attackers = board.attackers(self.color, enemy_king_square)
            if enemy_king_attackers:
                attacker_square = enemy_king_attackers.pop()
                capture_move = chess.Move(attacker_square, enemy_king_square)
                return capture_move
        return None