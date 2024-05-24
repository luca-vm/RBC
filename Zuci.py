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
import time
import math

class Zuci(Player):

    def __init__(self):
        self.board = None
        self.color = None
        self.sense_counter = 0
        self.board_states = set()
        self.opp_board_states = set()
        self.my_piece_captured_square = None
        self.my_piece_captured = None
        self.sense = None
        self.first_turn = True
        self.engine = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)
        self.engine_opponent = chess.engine.SimpleEngine.popen_uci('./stockfish.exe', setpgrp=True)

    def handle_game_start(self, color: Color, board: chess.Board, opponent_name: str):
        self.board = board
        self.color = color
        self.voting_confidence = None
        self.board_states = {board.fen()}
        
    def handle_opponent_move_result(self, captured_my_piece: bool, capture_square: Optional[Square]):  
        #  for capture sense
        self.my_piece_captured_square = capture_square
        if self.my_piece_captured_square:
            self.my_piece_captured = self.board.piece_at(capture_square)
        
        # capture sense
            
        self.stock_opp_sense()

        if self.color and self.first_turn:
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
      
        # in case en passant
        if self.my_piece_captured and self.my_piece_captured == chess.PAWN:
            # print("Pawn captured")
            return self.my_piece_captured_square
        
        # STRATEGY 1 
        # Sense based on capture
        if (self.my_piece_captured_square):
            # print("Sense using capture",self.my_piece_captured_square)
            self.sense = self.my_piece_captured_square
        

        # STRATEGY 2
        # Sense based on stock prediction
        # fix borders
        if self.sense is not None:
            x = self.sense % 8
            y = self.sense // 8
            
            if x == 0:
                x = 1
            elif x == 7:
                x = 6
            
            if y == 0:
                y = 1
            elif y == 7:
                y = 6
            
            self.sense = y * 8 + x
        # print("Sense square before", self.sense)
            
        if self.my_piece_captured_square:
            return self.sense
        
        highest_entropy_square = self.new_determine_entropy(self.board_states, self.sense)

        if highest_entropy_square is not None:
            x = highest_entropy_square % 8
            y = highest_entropy_square // 8
            
            if x == 0:
                x = 1
            elif x == 7:
                x = 6
            
            if y == 0:
                y = 1
            elif y == 7:
                y = 6
            
            highest_entropy_square = y * 8 + x
        else:
            highest_entropy_square = self.sense

        # print("highest entropy square is : ", highest_entropy_square)
        return highest_entropy_square
            
    def stock_opp_sense(self):
        
        if self.color and self.first_turn:
            self.first_turn = False
            # print("first turn")
            self.sense = chess.E4
        
        
        # Swap player/color/turn
        self.color = not self.color
        opp_move = self.choose_opp_move()
        self.color = not self.color
        if opp_move:
            self.sense = chess.parse_square((opp_move.uci())[2:4])
        else:
            self.sense = chess.E4
        # print("Sense after parse is : ",self.sense)      
            
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
            # print("Filtered to 0")
            self.save_filtered_states(rejected_states)
    
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
             
    def choose_opp_move(self):
         
        opp_states = self.board_states.copy()
        # print("Opponent states = ", len(opp_states))
        # Limit the number of board states to 10000
        if len(opp_states) > 10000:
            opp_states = set(random.sample(list(opp_states), 10000))
      
        # Calculate the time limit for each board
        time_limit = 10 / (len(opp_states))

        # Collect the moves suggested by Stockfish for each board state
        suggested_moves = []
      
        for state in opp_states:
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
                result = self.engine_opponent.play(board, chess.engine.Limit(time=time_limit))
                if (result.move):
                    suggested_moves.append(result.move.uci())
                else:
                    suggested_moves.append("0000")
       
        # Count the occurrences of each valid move
        move_counts = Counter(suggested_moves)

        # Select the most common valid move
        max_count = max(move_counts.values())
        self.voting_confidence = max_count/len(suggested_moves)*100
        # print("Percent of votes : ", max_count/len(suggested_moves)*100)
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
            self.engine_opponent.quit()
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



# NEW ENTROPY METHODS
    def new_determine_entropy(self, board_states, square):
        max_entropy = -math.inf
        max_entropy_square = None

        # Calculate the rank and file of the original square
        rank = square // 8
        file1 = square % 8

        # Define the relative positions of the neighboring squares
        neighbor_positions = [
            (-1, -1), (-1, 0), (-1, 1),
            (0, -1), (0, 0), (0, 1),
            (1, -1), (1, 0), (1, 1)
        ]

        for row_offset, col_offset in neighbor_positions:
            # Calculate the rank and file of the neighboring square
            neighbor_rank = rank + row_offset
            neighbor_file = file1 + col_offset

            # Check if the neighboring square is within the chessboard bounds
            if 0 < neighbor_rank < 8 and 0 < neighbor_file < 8:
                neighbor_square = neighbor_rank * 8 + neighbor_file
                entropy = self.calculate_3x3_entropy(board_states, neighbor_square)

                if entropy > max_entropy:
                    max_entropy = entropy
                    max_entropy_square = neighbor_square

        return max_entropy_square

    def calculate_3x3_entropy(self, board_states, square):
        # 3x3 variance matrix
        variance_matrix = [[0 for _ in range(3)] for _ in range(3)]

        # Calculate the rank and file of the top-left corner of the 3x3 grid
        rank = square // 8
        file1 = square % 8
        top_left_rank = max(0, rank - 1)
        top_left_file = max(0, file1 - 1)

        for row in range(3):
            for col in range(3):
                pieces = []
                for state in board_states:
                    board = chess.Board(state)
                    board.turn = not self.color
                    board = rutils.without_opponent_pieces(board)

                    # Calculate the index of the square in the 3x3 grid
                    grid_rank = top_left_rank + row
                    grid_file = top_left_file + col

                    # Check if the square is within the chessboard bounds
                    if 0 < grid_rank < 8 and 0 < grid_file < 8:
                        index = grid_rank * 8 + grid_file
                        piece = board.piece_at(index)
                        pieces.append(piece)

                variance_matrix[row][col] = self.calculate_entropy(pieces)

        return sum(sum(row) for row in variance_matrix)

    def calculate_entropy(self, pieces):
        piece_counts = Counter(pieces)
        total = len(pieces)
        entropy = 0
        for count in piece_counts.values():
            probability = count / total
            entropy -= probability * math.log2(probability)
        return entropy

    def entropy_averages(self, variance_matrix):
        highest = -math.inf
        highest_cell = (0, 0)

        for row in range(3):
            for col in range(3):
                entropy = variance_matrix[row][col]
                if entropy > highest:
                    highest = entropy
                    highest_cell = (row, col)

        # Calculate the index of the highest entropy cell relative to self.sense
        sense_rank = self.sense // 8
        sense_file = self.sense % 8
        highest_entropy_square = (sense_rank + highest_cell[0] - 1) * 8 + (sense_file + highest_cell[1] - 1)

        # Check if the highest_entropy_square is within the chessboard bounds
        if not (0 <= highest_entropy_square < 64):
            # If the square is out of bounds, return self.sense as the default
            return self.sense

        return highest_entropy_square
    
    
