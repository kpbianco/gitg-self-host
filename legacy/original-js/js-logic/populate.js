import prompt from 'prompt-sync';
// const prompt = require("prompt-sync")();
import { tags } from './tags.js';
import { tag_groups } from './tag_groups.js';
import { values_list } from './values.js';
import { goals_list } from './goals.js';
import { lifes } from './life.js';
import { focuses } from './focuses.js';
import { tasks } from './tasks.js';

function tag_groups_from_groups_tags(tag) {
  var groups_with_tag = [];
  for (const [key, value] of tag_groups) {
    if (value.tags.includes(tag) && !groups_with_tag.includes(key)) {
      groups_with_tag.push(key);
    }
  }
  return groups_with_tag;
}

function updateAllTagsWithGroups() {
  for (const [tag, tagData] of tags) {
    const groupsForTag = tag_groups_from_groups_tags(tag);
    // Update the groups in the tagData
    tagData.group = groupsForTag;
  }
}

function updateTaskGroups(taskData) {
  const groupsWithTag = [];
  for (const tag of taskData.tags) {
    for (const [group, groupData] of tag_groups) {
      if (groupData.tags.includes(tag) && !groupsWithTag.includes(group)) {
        groupsWithTag.push(group);
      }
    }
  }
  return groupsWithTag;
}

// Function to update all tasks with their associated groups
function updateAllTasksWithGroups() {
  for (const [task, taskData] of tasks) {
    const groupsForTask = updateTaskGroups(taskData);
    // Update the groups in the taskData
    taskData.groups = groupsForTask;
  }
}

function populateGroupTotalTasks() {
  // Reset task_count for each group
  for (const groupData of tag_groups.values()) {
    groupData.total_tasks = 0;
  }

  // Iterate through each task
  for (const [, taskData] of tasks) {
    // Iterate through the groups associated with the task
    for (const group of taskData.groups) {
      if (tag_groups.has(group)) {
        tag_groups.get(group).total_tasks += 1;
      }
    }
  }
}

function deepCopy(obj) {
  if (obj === null || typeof obj !== 'object') {
    return obj;
  }

  if (obj instanceof Date) {
    return new Date(obj);
  }

  if (obj instanceof Array) {
    return obj.map((item) => deepCopy(item));
  }

  if (obj instanceof Map) {
    const copy = new Map();
    for (let [key, value] of obj) {
      copy.set(key, deepCopy(value));
    }
    return copy;
  }

  if (obj instanceof Set) {
    const copy = new Set();
    for (let item of obj) {
      copy.add(deepCopy(item));
    }
    return copy;
  }

  if (typeof obj === 'object') {
    const copy = {};
    for (let key in obj) {
      if (obj.hasOwnProperty(key)) {
        copy[key] = deepCopy(obj[key]);
      }
    }
    return copy;
  }
}

function populateTagTotalTasks() {
  // Reset task_count for each tag
  for (const tagData of tags.values()) {
    tagData.total_tasks = 0;
  }

  // Iterate through each task
  for (const [, taskData] of tasks) {
    // Iterate through the tags associated with the task
    for (const tag of taskData.tags) {
      if (tags.has(tag)) {
        tags.get(tag).total_tasks += 1;
      }
    }
  }
}

function update_tags_in_group(groupName, newScore) {
  // Iterate over all tags in the tags map
  for (const [tagName, tagObject] of tags) {
    // Check if the tag belongs to the specified group
    if (tagObject.group.includes(groupName)) {
      // Update the tag's score with the new score
      tagObject.score += newScore;
    }
  }
}

function add_to_tag(iterable, adder, newScore) {
  for (const ad of adder) {
    for (const add of iterable.get(ad)) {
      if (tags.get(add)) {
        tags.get(add).score += newScore;
      }
    }
  }
}

function values_add(vals, newScore) {
  for (const val in vals) {
    for (const v of values_list.get(val)) {
      if (tags.get(v)) {
        tags.get(v).score += newScore;
      }
    }
  }
}

function archetype_add(archetype) {
  if (archetype == 'ISTP') {
    update_tags_in_group('Feeling', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Intuitive', 0.75);
  } else if (archetype == 'ESTP') {
    update_tags_in_group('Intuitive', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Intuitive', 0.75);
  } else if (archetype == 'INTP') {
    update_tags_in_group('Feeling', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Sensing', 0.75);
  } else if (archetype == 'ENTP') {
    update_tags_in_group('Sensing', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Feeling', 0.75);
  } else if (archetype == 'ISFP') {
    update_tags_in_group('Thinking', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Intuitive', 0.75);
  } else if (archetype == 'ESFP') {
    update_tags_in_group('Intuitive', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Thinking', 0.75);
  } else if (archetype == 'ISTJ') {
    update_tags_in_group('Intuitive', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Feeling', 0.75);
  } else if (archetype == 'ESTJ') {
    update_tags_in_group('Feeling', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Intuitive', 0.75);
  } else if (archetype == 'INFP') {
    update_tags_in_group('Thinking', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Sensing', 0.75);
  } else if (archetype == 'ENFP') {
    update_tags_in_group('Sensing', 1.0);
    update_tags_in_group('Judging', 0.75);
    update_tags_in_group('Thinking', 0.75);
  } else if (archetype == 'INFJ') {
    update_tags_in_group('Sensing', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Thinking', 0.75);
  } else if (archetype == 'ENFJ') {
    update_tags_in_group('Thinking', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Sensing', 0.75);
  } else if (archetype == 'ISFJ') {
    update_tags_in_group('Intuitive', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Thinking', 0.75);
  } else if (archetype == 'ESFJ') {
    update_tags_in_group('Thinking', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Intuitive', 0.75);
  } else if (archetype == 'ENTJ') {
    update_tags_in_group('Feeling', 1.0);
    update_tags_in_group('Perceiving', 0.75);
    update_tags_in_group('Sensing', 0.75);
  } else if (archetype == 'INTJ') {
    update_tags_in_group('Sensing', 1.0);
    update_tags_in_group('Feeling', 0.75);
    update_tags_in_group('Perceiving', 0.75);
  }
}

function enneagram_add(enneagram, wing) {
  if (enneagram == 'Enneagram_1') {
    update_tags_in_group('Enneagram_1', 1.0);
    if (wing == 'Enneagram_2') {
      update_tags_in_group('Enneagram_2', 0.75);
    } else {
      update_tags_in_group('Enneagram_9', 0.75);
    }
  } else if (enneagram == 'Enneagram_2') {
    update_tags_in_group('Enneagram_2', 1.0);
    if (wing == 'Enneagram_1') {
      update_tags_in_group('Enneagram_1', 0.75);
    } else {
      update_tags_in_group('Enneagram_3', 0.75);
    }
  } else if (enneagram == 'Enneagram_3') {
    update_tags_in_group('Enneagram_3', 1.0);
    if (wing == 'Enneagram_2') {
      update_tags_in_group('Enneagram_2', 0.75);
    } else {
      update_tags_in_group('Enneagram_4', 0.75);
    }
  } else if (enneagram == 'Enneagram_4') {
    update_tags_in_group('Enneagram_4', 1.0);
    if (wing == 'Enneagram_3') {
      update_tags_in_group('Enneagram_3', 0.75);
    } else {
      update_tags_in_group('Enneagram_5', 0.75);
    }
  } else if (enneagram == 'Enneagram_5') {
    update_tags_in_group('Enneagram_5', 1.0);
    if (wing == 'Enneagram_4') {
      update_tags_in_group('Enneagram_4', 0.75);
    } else {
      update_tags_in_group('Enneagram_6', 0.75);
    }
  } else if (enneagram == 'Enneagram_6') {
    update_tags_in_group('Enneagram_6', 1.0);
    if (wing == 'Enneagram_5') {
      update_tags_in_group('Enneagram_5', 0.75);
    } else {
      update_tags_in_group('Enneagram_7', 0.75);
    }
  } else if (enneagram == 'Enneagram_7') {
    update_tags_in_group('Enneagram_7', 1.0);
    if (wing == 'Enneagram_6') {
      update_tags_in_group('Enneagram_6', 0.75);
    } else {
      update_tags_in_group('Enneagram_8', 0.75);
    }
  } else if (enneagram == 'Enneagram_8') {
    update_tags_in_group('Enneagram_8', 1.0);
    if (wing == 'Enneagram_7') {
      update_tags_in_group('Enneagram_7', 0.75);
    } else {
      update_tags_in_group('Enneagram_9', 0.75);
    }
  } else if (enneagram == 'Enneagram_9') {
    update_tags_in_group('Enneagram_9', 1.0);
    if (wing == 'Enneagram_8') {
      update_tags_in_group('Enneagram_8', 0.75);
    } else {
      update_tags_in_group('Enneagram_1', 0.75);
    }
  }
}

function sigmoid(x) {
  return 1 / (1 + Math.exp(-x));
}

function sigmoid_tags() {
  // Iterate through each tag in the tags map
  for (const [tagName, tagObject] of tags) {
    // Apply the sigmoid function to the current score
    tagObject.score = sigmoid(tagObject.score);
  }
}

updateAllTagsWithGroups();
updateAllTasksWithGroups();
populateGroupTotalTasks();
populateTagTotalTasks();

//test results go here, the values(except strings) and exact function call count stays same
archetype_add('ISTP');
enneagram_add('Enneagram_7', 'Enneagram_8');
add_to_tag(focuses, ['Growth_focused'], 0.5);
add_to_tag(values_list, ['Discipline', 'Independence', 'Honesty', 'Freedom', 'Education'], 0.75);
add_to_tag(goals_list, ['Financially_Free', 'Control_your_mindset', 'Better_relationships'], 1.0);
add_to_tag(lifes, ['Standard/modest'], 0.5);
sigmoid_tags();
const activeTasks = deepCopy(tasks);

export { tags, tag_groups, activeTasks };
