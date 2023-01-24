# monad-rekry2023
This is my solution for the Monad Oy recruiment code puzzle.
</br>
## Solution
- Creates random paths for the plane trying to find the target airport with the proper approach.
- If it goes over bounds or uses too many steps, it begins again from the start.
- In one plane configuration, the target is to find as many possible routes as possible for that plane.
- If there are multiple planes, routes are created one at the time. Only when all of the planes have found their routes without collisions, the search has been a success. The plan is to find as many solutions where all of the planes will land.
- There is a 25 seconds time limit, and after that the route with the lowest score is chosen. If there are no solutions found in that time, an empty command is sent, and the planes will not change their courses at all.
- Takes information of planes, airports, and sky area.
- Is not made specifically for any of the levels, and should work on different configurations as well. (Won't probably handle larger sky area that well)
- The routes are not (atleast yet) optimized in any way. They have no preference towards min or max direction change, or towards their target. It's all random.

## My highscores
1st Steps = 72 </br>
Turning = 82 </br>
Loop Around = 78 </br>
Multiplane = 141 </br>
Criss Cross = 202 </br>
Wrong Way = 70 </br>
Don't Crash = 142 </br>
Plane Hold'em = 312
