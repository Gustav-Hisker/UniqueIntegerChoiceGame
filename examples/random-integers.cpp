#include<iostream>
#include <random> // for the randomness
#include <vector>

int main(){
    // read n, k, w and j
    int n, k, w, j;
    std::cin >> n >> k >> w >> j;

    // creating a random device
    std::random_device rand_dev;
    // creating a random generator
    std::mt19937 gen(rand_dev());
    // creating distribution
    std::uniform_int_distribution<int> distr(1, k);

    // repeating for the whole game
    while (true){
        // outputting random integer
        std::cout << distr(gen) << std::endl;
        // reading the input but ignoring it
        std::vector<int> submitted_numbers(n);
        for (int i = 0; i < n; i++) {
            std::cin >> submitted_numbers[i];
        }
    }
}