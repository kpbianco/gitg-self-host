import path from 'path';
import { mapping } from './mapping.js'; // Importing the mapping file

export function createPerson() {
  return {
    mbti: null,
    enneagram: null,
    phase: null,
  };
}

export function SetType(person, enneagram, mbti) {
  person.mbti = mbti;
  person.enneagram = enneagram;
}

export function UpdatePhase(person, phase) {
  person.phase = phase;
}

export function parseSection(content, section) {
  const regex = new RegExp(`${section}[\\s\\S]*?(?=\n###|$)`);
  const match = content.match(regex);
  return match ? match[0].trim() : '';
}

// Dynamically load JSON or object from a .js file
async function loadJSObject(filePath) {
  try {
    const absolutePath = path.resolve(filePath);
    const module = await import(absolutePath);
    return module.default;
  } catch (error) {
    console.error(`Error loading file ${filePath}: ${error.message}`);
    return null;
  }
}

// Make this function async
async function createPersonDictionary(user) {
  const mbtiFilePath = `./mbti/${user.mbti}.cjs`;
  const enneagramFilePath = `./enneagram/enneagram_${user.enneagram}.cjs`;

  // Await both promises
  const mbtiData = await loadJSObject(mbtiFilePath);
  const enneagramData = await loadJSObject(enneagramFilePath);

  if (!mbtiData || !enneagramData) {
    console.error('Error: Could not load data for the user.');
    return null;
  }

  const personData = {};

  // Helper to merge fields dynamically
  function mergeFields(fieldName) {
    const mbtiField = mbtiData[fieldName] || {};
    const enneagramField = enneagramData[fieldName] || {};

    // Merge shared keys or add exclusive ones
    const mergedField = {};
    const allKeys = new Set([...Object.keys(mbtiField), ...Object.keys(enneagramField)]);
    allKeys.forEach((key) => {
      const mbtiValue = mbtiField[key];
      const enneagramValue = enneagramField[key];

      if (Array.isArray(mbtiValue) && Array.isArray(enneagramValue)) {
        mergedField[key] = [...mbtiValue, ...enneagramValue];
      } else if (mbtiValue && enneagramValue) {
        mergedField[key] = `${mbtiValue}\n${enneagramValue}`;
      } else {
        mergedField[key] = mbtiValue || enneagramValue;
      }
    });

    return mergedField;
  }

  // Merge `coreCharacteristics`
  personData.coreCharacteristics = mergeFields('coreCharacteristics');

  // Merge phases dynamically
  personData.phases = [];
  user.phases.forEach((phaseNumber) => {
    const mbtiPhase = mbtiData.phases.find((p) => p.phase === phaseNumber) || {};
    const enneagramPhase = enneagramData.phases.find((p) => p.phase === phaseNumber) || {};

    const mergedPhase = {};
    const allKeys = new Set([...Object.keys(mbtiPhase), ...Object.keys(enneagramPhase)]);
    allKeys.forEach((key) => {
      const mbtiValue = mbtiPhase[key];
      const enneagramValue = enneagramPhase[key];

      if (Array.isArray(mbtiValue) && Array.isArray(enneagramValue)) {
        mergedPhase[key] = [...mbtiValue, ...enneagramValue];
      } else if (mbtiValue && enneagramValue) {
        mergedPhase[key] = `${mbtiValue}\n${enneagramValue}`;
      } else {
        mergedPhase[key] = mbtiValue || enneagramValue;
      }
    });

    personData.phases.push(mergedPhase);
  });

  return personData;
}

function formatPersonData(personData, enneagramType, mbtiType, phasesToInclude = Infinity) {
  // Fetch enneagram adjective and mbti noun
  const enneagramAdjective = mapping.enneagram[enneagramType];
  const mbtiNoun = mapping.mbti[mbtiType];
  const combinedHeader = `${enneagramAdjective} ${mbtiNoun}`;

  let output = `**${combinedHeader}**\n\n`;

  // Print Core Characteristics
  if (personData.coreCharacteristics) {
    output += `**Core Characteristics**\n\n`;
    for (const [key, value] of Object.entries(personData.coreCharacteristics)) {
      output += `**${capitalize(key)}**:\n`;
      output += formatValueToPlaintext(value);
      output += `\n`;
    }
  }

  // Print Phases up to the specified number
  if (personData.phases && Array.isArray(personData.phases)) {
    personData.phases
      .filter((phase) => phase.phase <= phasesToInclude)
      .forEach((phase) => {
        output += `\n**Phase ${phase.phase}: ${phase.title}**\n\n`;
        output += `**Goal**: ${phase.goal}\n\n`;
        output += `**Key Takeaways**:\n`;
        output += formatValueToPlaintext(phase.keyTakeaways);
        output += `\n\n**Actions**:\n`;
        output += formatValueToPlaintext(phase.actions);
        if (phase.exampleExercise) {
          output += `\n\n**Example Exercise**: ${phase.exampleExercise}`;
        }
        if (phase.dont) {
          output += `\n\n**Don't**: ${formatValueToPlaintext(phase.dont)}`;
        }
        output += `\n`;
      });
  }

  return output;
}

function formatValueToPlaintext(value) {
  if (Array.isArray(value)) {
    return value.map((item) => `- ${item}`).join('\n');
  }
  return value;
}

function capitalize(string) {
  return string.charAt(0).toUpperCase() + string.slice(1);
}

// Example Usage
const user = {
  mbti: 'ISTP',
  enneagram: 8,
  phases: [1, 2, 3],
};

// Wrap in async IIFE or use in an async context
(async () => {
  const personData = await createPersonDictionary(user);
  if (personData) {
    console.log(formatPersonData(personData, user.enneagram, user.mbti, 3));
  }
})();
