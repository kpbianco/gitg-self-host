//imports
import YAML from 'yaml';
import fs from 'fs';

//load file
const file = fs.readFileSync('./task_list.yaml', 'utf8');
let taskfile = YAML.parse(file);

//english file open and task_map_en
let tasks_en = taskfile['en']['tasklist'];
const task_map_en = new Map();

// task_map_enh
try {
  // Populate the task_map_en
  for (const [key, values] of Object.entries(tasks_en)) {
    values.forEach((value) => {
      if (!task_map_en[value]) {
        task_map_en[value] = [];
      }
      task_map_en[value].push(key);
    });
  }

  // Log the task_map_en to the console
  console.log(task_map_en);
} catch (e) {
  console.error(e);
}

function getTasksByTag(task, tasklist_lang) {
  let retVal;
  try {
    retVal = tasklist_lang[task];
  } catch (e) {
    retVal = -1;
  }
  return retVal;
}

var inputs = [
  ['Introverted', 'Assertive', 'Rational', 'Concrete', 'Structured'],
  [
    'extrovert',
    'emotional',
    'impulse',
    'abstract',
    'structured',
    'reserved',
    'rational',
    'concrete',
    'assertive',
    'introvert',
  ],
  ['Christian', 'male', 'moderate'],
  [
    'Financially free/successful',
    'Religious follower',
    'Find your purpose',
    'Strengthen your discipline',
    'Control your mindset',
    'Europe',
    'Humble/minimalist',
    'Pursuit of interests',
    'Efficiency',
    'Equality',
    'Ethics',
    'Faith',
    'Family',
  ],
];

console.log(getTasksByTag('Abstract', task_map_en));
//console.log(task_en_map)

//will refactor this to switch from Task=>Tag to Tag=>Task
