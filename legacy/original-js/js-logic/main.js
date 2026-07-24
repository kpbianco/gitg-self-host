import { tags } from './populate.js'
import {tag_groups} from './populate.js'
import {activeTasks} from './populate.js'

var complete_tasks = []

function findGroup(tag) {
    for (let [group, groupData] of tag_groups) {
        if (groupData.tags.includes(tag)) {
            return group;
        }
    }
}

function updateTagScores(tag) {
    var curr_score = tags.get(tag).score;
    var task_ratio = tags.get(tag).tasks_complete / tags.get(tag).total_tasks;
    var new_score = curr_score * ((1 - task_ratio)**0.25);
    tags.get(tag).score = new_score;
}

function updateGroupScores(group) {
    let totalTasksRemaining = 0;

    // First, calculate the total remaining tasks for the group
    for (const tagName of tag_groups.get(group).tags) {
        const tag = tags.get(tagName);
        if (tag) {
            totalTasksRemaining += (tag.total_tasks - tag.tasks_complete);
        }
    }

    // Now calculate the group score
    let groupScore = 0;
    
    for (const tagName of tag_groups.get(group).tags) {
        const tag = tags.get(tagName);
        if (tag && totalTasksRemaining > 0) {
            const tasksRemaining = tag.total_tasks - tag.tasks_complete;
            const weight = tasksRemaining / totalTasksRemaining;
            groupScore += tag.score * weight;
        }
    }

    // Update the group's score with the calculated value
    tag_groups.get(group).score = groupScore;
}

function updateAllTaskScores() {
    for (const [taskName, task] of activeTasks) {
        let totalTasksSum = 0;
        let weightedScoreSum = 0;

        // Iterate over each group in the task
        for (const group of task.groups) {
            let groupTotalTasks = 0;
            let groupScoreSum = 0;
            let groupTagCount = 0;

            // Iterate over each tag in the task's tags
            for (const tag of task.tags) {
                // Check if the tag belongs to the current group
                if (tags.has(tag) && tag_groups.has(group)) {
                    const tagObject = tags.get(tag);
                    if (tagObject.group.includes(group)) {
                        groupScoreSum += tagObject.score;
                        groupTagCount++;
                    }
                }
            }

            if (groupTagCount > 0) {
                const groupMeanScore = groupScoreSum / groupTagCount;
                groupTotalTasks = tag_groups.get(group).total_tasks;

                totalTasksSum += groupTotalTasks;
                weightedScoreSum += groupMeanScore * groupTotalTasks;
            }
        }

        // Calculate the final score for the task
        const finalTaskScore = weightedScoreSum / totalTasksSum;

        // Update the task's score in the tasks map
        task.score = finalTaskScore;
    }
}

// Function to finish a task
function finish_task(taskName) {
    const task = activeTasks.get(taskName);
    if (!task) {
        console.error(`Task ${taskName} not found.`);
        return;
    }
    // Remove from pool (pop task from a copy of tasks)
    activeTasks.delete(taskName); // Simulate "popping" the task from the pool

    // Increment completed for all tags in the task
    for (const tag of task.tags) {
        if (tags.has(tag)) {
            tags.get(tag).tasks_complete += 1;
            updateTagScores(tag);
        }
    }

    // Update groups tasks complete
    for (const group of task.groups) {
        if (tag_groups.has(group)) {
            tag_groups.get(group).tasks_complete += 1;
            updateGroupScores(group);
        }
    }

    // Append the finished task to the finished_tasks list
    complete_tasks.push({ [taskName]: JSON.parse(JSON.stringify(task)) });

    // Call other update functions (assuming they are defined)
    updateAllTaskScores()
}

// Example usage with the tasks map

function getNextTask() {
    let highestScoringTask = null;
    let highestScore = -Infinity;

    for (const [taskName, task] of activeTasks) {
        if (task.score > highestScore) {
            highestScore = task.score;
            highestScoringTask = taskName;
        }
    }

    return highestScoringTask;
}

function updateAllGroupScores() {
    for (const [groupName, group] of tag_groups) {
        updateGroupScores(groupName);
    }
}


//MAIN()()()()
//setup
updateAllGroupScores()
updateAllTaskScores()

//User has started using application
console.log(getNextTask())
finish_task(getNextTask())
console.log(getNextTask())
finish_task(getNextTask())
console.log(getNextTask())
