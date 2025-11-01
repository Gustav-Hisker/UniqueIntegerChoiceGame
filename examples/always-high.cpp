#include<iostream>
#include <vector>

int main(){
    // read n, k, w and j
    int n, k, w, j;
    std::cin >> n >> k >> w >> j;

    // repeating for the whole game
    while (true){
        // outputting the highest number
        std::cout << k << std::endl;
        // reading the input but ignoring it
        std::vector<int> submitted_numbers(n);
        for (int i = 0; i < n; i++) {
            std::cin >> submitted_numbers[i];
        }
    }
}