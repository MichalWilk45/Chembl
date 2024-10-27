#!/bin/bash

board=(1 2 3 4 5 6 7 8 9)
save_file="savefile_tic_tac_toe.txt"


save_game() {
    echo "${board[@]}" > "$save_file"
    echo "$turn" >> "$save_file"
    echo "Save Complete"
}

computer_move() {
    # Collect all available positions
    available_moves=()
    for i in "${!board[@]}"; do
        if [[ "${board[$i]}" != "X" && "${board[$i]}" != "O" ]]; then
            available_moves+=($i)
        fi
    done

    # Choose a random move from available spots
    local random_index=$((RANDOM % ${#available_moves[@]}))
    local move=${available_moves[$random_index]}
    board[$move]="O"
    echo "Computer chose position $((move + 1))"
}

load_game() {
    if [[ -f $save_file ]]; then
        saved_data=()
        while IFS= read -r line; do
            saved_data+=("$line")
        done < "$save_file"
        board=(${saved_data[0]})
        turn="${saved_data[1]}"
        echo "Game loaded"
    else
        echo "No save data"
    fi
}
display_board() {
    echo "${board[0]} | ${board[1]} | ${board[2]}"
    echo "${board[3]} | ${board[4]} | ${board[5]}"
    echo "${board[6]} | ${board[7]} | ${board[8]}"

}

check_winner() {
    local win_combo=(
        "0 1 2" "3 4 5" "6 7 8" #rows
        "0 3 6" "1 4 7" "2 5 8" #columns
        "0 4 8" "2 4 6" #diagonals
    )

    for combo in "${win_combo[@]}"; do
        set -- $combo
        if [[ "${board[$1]}" == "${board[$2]}" && "${board[$2]}" == "${board[$3]}" ]]; then
            display_board
            echo "Player ${board[$1]} wins"
            rm -f "$save_file" 
            exit 0
        fi
    done
}

turn="X"

echo "Do you want to load data? (y/n)"
read -r load_choice
if [[ "$load_choice" == "y" ]]; then
    load_game
fi

echo "Press 1 to play with computer"
read -r game_mode

for ((i=1; i<=9; i++)); do
    display_board
    echo "Player $turn, choose your move 1-9 or s for save"
    read -r move
    if [[ "$move" == "s" ]]; then
        save_game
        exit 0
    fi

    move=$((move-1))
    if [[ "${board[$move]}" != "X" && "${board[$move]}" != "O" ]]; then
        board[$move]=$turn
        check_winner
        if [[ $turn == "X"  && $game_mode != 1 ]]; then
            turn="O"
        else
            turn="X"
        fi
    else
        echo "Invalid move, try again"
            ((i--))
    fi
    if [[ $game_mode == 1 ]]; then
        computer_move
        check_winner
        #turn="X" 
    fi
done

display_board
echo "its s draw"