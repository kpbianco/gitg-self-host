import promptSync from 'prompt-sync';
const promptFn = promptSync();

function generateCombinations() {
  const fields = [
    ['Extroverted', 'Introverted'],
    ['Assertive', 'Reserved'],
    ['Emotional', 'Rational'],
    ['Concrete', 'Abstract'],
    ['Impulsive', 'Structured'],
  ];

  const combinations = [];

  for (const e0 of fields[0]) {
    for (const e1 of fields[1]) {
      for (const e2 of fields[2]) {
        for (const e3 of fields[3]) {
          for (const e4 of fields[4]) {
            combinations.push([e0, e1, e2, e3, e4]);
          }
        }
      }
    }
  }

  return combinations;
}

// Example usage
const archetypes = generateCombinations();

function find_choice(array, subarray) {
  let value = -1;
  for (let i = 0; i < array.length; i++) {
    let match = 0;
    for (let j = 0; j < array[0].length; j++) {
      if (array[i][j] === subarray[j]) {
        match++;
      }
      if (match === 5) {
        value = i;
      }
    }
  }
  return value;
}

promptFn(
  "Welcome to the archetype test.\n Please answer the following questions from 1-5 on likelihood of it representing you, with 1 being not like you at all, and 5 being like you entirely. \n Press 'enter' to continue\n"
);

let ret;
let introvert_score = 0.0;
let extrovert_score = 0.0;
let assertive_score = 0.0;
let reserved_score = 0.0;
let emotional_score = 0.0;
let rational_score = 0.0;
let concrete_score = 0.0;
let abstract_score = 0.0;
let impulsive_score = 0.0;
let structured_score = 0.0;
let enneagram_1_score = 0.0;
let enneagram_2_score = 0.0;
let enneagram_3_score = 0.0;
let enneagram_4_score = 0.0;
let enneagram_5_score = 0.0;
let enneagram_6_score = 0.0;
let enneagram_7_score = 0.0;
let enneagram_8_score = 0.0;
let enneagram_9_score = 0.0;

// MBTI Section (25 Questions)
// Introversion vs Extroversion, Thinking vs Feeling, Sensing vs Intuition, Judging vs Perceiving

// 1
ret = promptFn('I find that my social battery runs out after long periods with others.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Needs solitude

// 2
ret = promptFn('I jump into tasks quickly without extensive planning.\n');
impulsive_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Action-oriented

// 3
ret = promptFn('I prefer thinking about the future over focusing on the present moment.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Visionary and introspective

// 4
ret = promptFn('When things go wrong, I rely on logic over emotion to solve problems.\n');
rational_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Values logic

// 5
ret = promptFn('I enjoy providing comfort to others when they are struggling.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: Empathetic and nurturing

// 6
ret = promptFn('In group discussions, I tend to listen more than speak.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Avoids spotlight

// 7
ret = promptFn('I take charge if no one else steps up with a good plan.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Bold leadership

// 8
ret = promptFn('I prefer routines over spontaneous decisions.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Prefers order

// 9
ret = promptFn('I avoid conflict even when I know I am right.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Avoids conflict

// 10
ret = promptFn('You prefer to solve practical problems instead of creative ones.\n');
concrete_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Practical mindset

// 11
ret = promptFn('I prefer meaningful conversations over small talk.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Seeks depth

// 12
ret = promptFn('I am known for being spontaneous and fun-loving.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Energetic

// 13
ret = promptFn('I prioritize logic over emotions when making decisions.\n');
rational_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Values rationality

// 14
ret = promptFn('You seek success through achievements.\n');
enneagram_3_score += parseFloat(ret) / 5.0;
assertive_score += parseFloat(ret) / 5.0; // ISTP assertiveness with Type 3 traits

// 15
ret = promptFn('I often worry about worst-case scenarios.\n');
enneagram_6_score += parseFloat(ret) / 5.0;
reserved_score += parseFloat(ret) / 5.0; // Type 6: Security-seeking

// 16
ret = promptFn('I feel energized after spending time alone.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Peace-seeking

// 17
ret = promptFn('I enjoy experimenting with new ideas or projects.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Curious and playful

// 18
ret = promptFn('I find it hard to let go of control when working on important tasks.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Control-oriented

// 19
ret = promptFn('I enjoy being recognized for my accomplishments.\n');
enneagram_3_score += parseFloat(ret) / 5.0;
assertive_score += parseFloat(ret) / 5.0; // Type 3: Achievement-focused

// 20
ret = promptFn('I thrive under high-pressure situations.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Thrives under pressure

// 21
ret = promptFn('I prefer to plan everything in advance rather than going with the flow.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Order-oriented

// 22
ret = promptFn('I tend to overthink decisions to avoid mistakes.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Overly cautious

// 23
ret = promptFn('I enjoy fast-paced environments and constant change.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Thrives on change

// 24
ret = promptFn('You prioritize kindness and empathy over logic.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: Empathy-driven

// 25
ret = promptFn('I struggle to relax when things feel unfinished.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Perfectionist tendencies

// 26
ret = promptFn('I find fulfillment in helping others.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: Finds purpose in service

// 27
ret = promptFn('I enjoy being challenged with complex problems.\n');
rational_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Values intellectual challenge

// 28
ret = promptFn('I avoid relying on others for emotional support.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Independent mindset

// 29
ret = promptFn("I get frustrated when others don't follow rules.\n");
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Rules-driven

// 30
ret = promptFn('You seek approval through your work or achievements.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_3_score += parseFloat(ret) / 5.0; // Type 3: Achievement-focused

// 31
ret = promptFn("I feel anxious when I'm not prepared.\n");
reserved_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Security-seeking

// 32
ret = promptFn('I enjoy being spontaneous and adventurous.\n');
impulsive_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Adventure-loving

// 33
ret = promptFn('I feel emotionally drained after socializing for too long.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Seeks peace and solitude

// 34
ret = promptFn('I value consistency and stability in my life.\n');
concrete_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Stability-driven

// 35
ret = promptFn('I enjoy leading others to achieve common goals.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Leadership-oriented

// 36
ret = promptFn('I often dream about achieving big things in life.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_3_score += parseFloat(ret) / 5.0; // Type 3: Ambitious and visionary

// 37
ret = promptFn('I am drawn to deep, meaningful conversations.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Seeks depth

// 38
ret = promptFn('I prefer working independently rather than in teams.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Values independence

// 39
ret = promptFn('I find it hard to forgive others easily.\n');
concrete_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Values justice

// 40
ret = promptFn('I tend to withdraw when I feel overwhelmed.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Avoids conflict

// 41
ret = promptFn('I feel happiest when surrounded by loved ones.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: Relationship-oriented

// 42
ret = promptFn('I enjoy solving puzzles and intellectual challenges.\n');
rational_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Analytical

// 43
ret = promptFn('I dislike being told what to do.\n');
impulsive_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Values autonomy

// 44
ret = promptFn('I often reflect on how things could have gone better.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Reflective and introspective

// 45
ret = promptFn('I find satisfaction in completing a task perfectly.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Perfectionist

// 46
ret = promptFn('I feel anxious about uncertain situations.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Values security

// 47
ret = promptFn('I enjoy challenging myself with new experiences.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Seeks excitement

// 48
ret = promptFn('I feel uncomfortable relying on others.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Independent

// 49
ret = promptFn('I strive to make a positive impact on the world.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_3_score += parseFloat(ret) / 5.0; // Type 3: Achievement-oriented

// 50
ret = promptFn('I value deep, personal connections with others.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Seeks emotional depth

// 51
ret = promptFn('I prefer stability over constant change.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Seeks stability

// 52
ret = promptFn('I often feel the need to be in control of situations.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Control-oriented

// 53
ret = promptFn('I enjoy exploring new ideas, even if they seem impractical.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Open to exploration

// 54
ret = promptFn('I get frustrated when people are disorganized or careless.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Values order

// 55
ret = promptFn('I tend to reflect on my emotions and try to understand them.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Introspective

// 56
ret = promptFn('You prefer working in a team over working alone.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Collaborative

// 57
ret = promptFn('I strive to perfect everything I do.\n');
structured_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Perfectionist

// 58
ret = promptFn('I often feel disconnected from others emotionally.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Emotionally distant

// 59
ret = promptFn('You enjoy inspiring others and leading them towards success.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_3_score += parseFloat(ret) / 5.0; // Type 3: Motivational leader

// 60
ret = promptFn('I value authenticity in both myself and others.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Authenticity-driven

// 61
ret = promptFn("I feel anxious when I don't have a plan in place.\n");
structured_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Anxiety-driven planning

// 62
ret = promptFn('You often jump from one idea to another without finishing them.\n');
impulsive_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Easily distracted

// 63
ret = promptFn('I feel most comfortable when I have time to myself.\n');
introvert_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Seeks peace

// 64
ret = promptFn('You prefer facts over feelings when making decisions.\n');
rational_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Values logic

// 65
ret = promptFn('I feel responsible for making sure everyone is happy.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: People-pleaser

// 66
ret = promptFn('I often struggle to express my emotions.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Emotionally reserved

// 67
ret = promptFn('You enjoy engaging in philosophical conversations.\n');
abstract_score += parseFloat(ret) / 5.0;
enneagram_5_score += parseFloat(ret) / 5.0; // Type 5: Philosophical mindset

// 68
ret = promptFn('I prefer to focus on one task at a time.\n');
concrete_score += parseFloat(ret) / 5.0;
enneagram_1_score += parseFloat(ret) / 5.0; // Type 1: Task-oriented

// 69
ret = promptFn('I feel uncomfortable when others challenge my ideas.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_6_score += parseFloat(ret) / 5.0; // Type 6: Avoids conflict

// 70
ret = promptFn('I often express my feelings openly to others.\n');
extrovert_score += parseFloat(ret) / 5.0;
enneagram_4_score += parseFloat(ret) / 5.0; // Type 4: Emotionally expressive

// 71
ret = promptFn('I value practical solutions over theoretical ideas.\n');
concrete_score += parseFloat(ret) / 5.0;
enneagram_8_score += parseFloat(ret) / 5.0; // Type 8: Pragmatic

// 72
ret = promptFn('You often make impulsive purchases or decisions.\n');
impulsive_score += parseFloat(ret) / 5.0;
enneagram_7_score += parseFloat(ret) / 5.0; // Type 7: Impulsive

// 73
ret = promptFn('I prefer staying in the background rather than taking the lead.\n');
reserved_score += parseFloat(ret) / 5.0;
enneagram_9_score += parseFloat(ret) / 5.0; // Type 9: Avoids leadership

// 74
ret = promptFn('I often find myself motivated by recognition and praise.\n');
assertive_score += parseFloat(ret) / 5.0;
enneagram_3_score += parseFloat(ret) / 5.0; // Type 3: Motivated by recognition

// 75
ret = promptFn('You feel a deep sense of purpose when helping others.\n');
emotional_score += parseFloat(ret) / 5.0;
enneagram_2_score += parseFloat(ret) / 5.0; // Type 2: Purpose-driven by service

let ft_ie, ft_ar, ft_ca, ft_er, ft_is;

if (introvert_score > extrovert_score) {
  ft_ie = 'Introverted';
} else {
  ft_ie = 'Extroverted';
}

if (impulsive_score > structured_score) {
  ft_is = 'Impulsive';
} else {
  ft_is = 'Structured';
}

if (concrete_score > abstract_score) {
  ft_ca = 'Concrete';
} else {
  ft_ca = 'Abstract';
}

if (emotional_score > rational_score) {
  ft_er = 'Emotional';
} else {
  ft_er = 'Rational';
}

if (assertive_score > reserved_score) {
  ft_ar = 'Assertive';
} else {
  ft_ar = 'Reserved';
}
const final_type = [ft_ie, ft_ar, ft_er, ft_ca, ft_is];

// Initialize Enneagram scores
let enneagram_scores = [
  enneagram_1_score,
  enneagram_2_score,
  enneagram_3_score,
  enneagram_4_score,
  enneagram_5_score,
  enneagram_6_score,
  enneagram_7_score,
  enneagram_8_score,
  enneagram_9_score,
];
// Sample function to assign core type and wing
function assignEnneagramWing(scores) {
  // Find the highest scoring type (core type)
  let core_type = scores.indexOf(Math.max(...scores)) + 1;

  // Determine adjacent types (possible wings)
  let wing1 = core_type === 1 ? 9 : core_type - 1;
  let wing2 = core_type === 9 ? 1 : core_type + 1;

  // Assign wing based on which adjacent type has a higher score
  let wing = scores[wing1 - 1] >= scores[wing2 - 1] ? wing1 : wing2;

  return { core_type, wing };
}

let { core_type, wing } = assignEnneagramWing(enneagram_scores);

console.log(`Core Type: ${core_type}, Wing: ${wing}`);

const final_scores = {
  introvert: introvert_score,
  extrovert: extrovert_score,
  assertive: assertive_score,
  reserved: reserved_score,
  emotional: emotional_score,
  rational: rational_score,
  concrete: concrete_score,
  abstract: abstract_score,
  impulse: impulsive_score,
  structured: structured_score,
  enn_1: enneagram_1_score,
  enn_2: enneagram_2_score,
  enn_3: enneagram_3_score,
  enn_4: enneagram_4_score,
  enn_5: enneagram_5_score,
  enn_6: enneagram_6_score,
  enn_7: enneagram_7_score,
  enn_8: enneagram_8_score,
  enn_9: enneagram_9_score,
};

function sortDictionaryKeysByValues(dictionary) {
  // Create an array of key-value pairs
  const keyValuePairs = Object.entries(dictionary);

  // Sort the array based on the values
  keyValuePairs.sort((a, b) => a[1] - b[1]);

  // Extract and return the keys from the sorted array
  return keyValuePairs.map((pair) => pair[0]);
}

let work_on = sortDictionaryKeysByValues(final_scores);
let idx = find_choice(archetypes, final_type);
console.log('final Type', final_type);
console.log('idx', idx);
let final_output = [archetypes[idx], work_on];
console.log('****' + final_output);

/* TDL
1. add 10 more questions so there is an even number of both categories
3. handle edge cases of ties
4. test assignment and code testing

*/
