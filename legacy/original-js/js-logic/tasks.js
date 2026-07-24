import fs from 'fs';
import yaml from 'js-yaml';
import path from 'path';

// Function to parse the YAML file and generate the task map
function generateTaskMap(yamlFilePath) {
    // Load the YAML file
    const yamlContent = fs.readFileSync(yamlFilePath, 'utf8');
    const data = yaml.load(yamlContent);

    // Initialize the tasks map
    const tasks = new Map();

    // Iterate through the task list in the YAML data
    for (const [task, tags] of Object.entries(data.en.tasklist)) {
        tasks.set(task, { tags, score: 0.0, groups: [] });
    }

    return tasks;
}

// Example usage
const yamlFilePath = './tasks.yaml';
const tasks = generateTaskMap(yamlFilePath);

// Output the tasks map to the console

export { tasks };