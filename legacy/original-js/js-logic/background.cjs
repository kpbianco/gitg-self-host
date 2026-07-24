import promptSync from 'prompt-sync';
const promptFn = promptSync();

let categories = [];
categories.push(['Christian', 'Male', 'Traditional']);
categories.push(['Christian', 'Female', 'Traditional']);
categories.push(['Christian', 'Other', 'Traditional']);
categories.push(['Christian', 'Male', 'Liberal']);
categories.push(['Christian', 'Female', 'Liberal']);
categories.push(['Christian', 'Other', 'Liberal']);
categories.push(['Spiritual', 'Male', 'Traditional']);
categories.push(['Spiritual', 'Female', 'Traditional']);
categories.push(['Spiritual', 'Other', 'Traditional']);
categories.push(['Spiritual', 'Male', 'Liberal']);
categories.push(['Spiritual', 'Female', 'Liberal']);
categories.push(['Spiritual', 'Other', 'Liberal']);
categories.push(['Non-religious', 'Male', 'Traditional']);
categories.push(['Non-religious', 'Female', 'Traditional']);
categories.push(['Non-religious', 'Other', 'Traditional']);
categories.push(['Non-religious', 'Male', 'Liberal']);
categories.push(['Non-religious', 'Female', 'Liberal']);
categories.push(['Non-religious', 'Other', 'Liberal']);
categories.push(['Buddhist', 'Male', 'Traditional']);
categories.push(['Buddhist', 'Female', 'Traditional']);
categories.push(['Buddhist', 'Other', 'Traditional']);
categories.push(['Buddhist', 'Male', 'Liberal']);
categories.push(['Buddhist', 'Female', 'Liberal']);
categories.push(['Buddhist', 'Other', 'Liberal']);
categories.push(['Islamic', 'Male', 'Traditional']);
categories.push(['Islamic', 'Female', 'Traditional']);
categories.push(['Islamic', 'Other', 'Traditional']);
categories.push(['Islamic', 'Male', 'Liberal']);
categories.push(['Islamic', 'Female', 'Liberal']);
categories.push(['Islamic', 'Other', 'Liberal']);
categories.push(['Jewish', 'Male', 'Traditional']);
categories.push(['Jewish', 'Female', 'Traditional']);
categories.push(['Jewish', 'Other', 'Traditional']);
categories.push(['Jewish', 'Male', 'Liberal']);
categories.push(['Jewish', 'Female', 'Liberal']);
categories.push(['Jewish', 'Other', 'Liberal']);
categories.push(['Taoist', 'Male', 'Traditional']);
categories.push(['Taoist', 'Female', 'Traditional']);
categories.push(['Taoist', 'Other', 'Traditional']);
categories.push(['Taoist', 'Male', 'Liberal']);
categories.push(['Taoist', 'Female', 'Liberal']);
categories.push(['Taoist', 'Other', 'Liberal']);
categories.push(['Hindu', 'Male', 'Traditional']);
categories.push(['Hindu', 'Female', 'Traditional']);
categories.push(['Hindu', 'Other', 'Traditional']);
categories.push(['Hindu', 'Male', 'Liberal']);
categories.push(['Hindu', 'Female', 'Liberal']);
categories.push(['Hindu', 'Other', 'Liberal']);

let religion = '';
let gender = '';
let political = '';

promptFn(
  'Welcome to the value framework test.\n Please answer the following questions with "yes" or "no". \n Press \'enter\' to continue\n'
);

let rel = promptFn('Do you consider yourself religious?');
rel = rel.toLowerCase().trim();
if (rel == 'no') {
  let spir = promptFn('Do you consider yourself spiritual?');
  spir = spir.toLowerCase().trim();
  if (spir == 'no') {
    religion = 'Non-religious';
  } else if (spir == 'yes') {
    religion = 'Spiritual';
  }
} else if (rel == 'yes') {
  let abr = promptFn('Is your religion mono-theistic?');
  abr = abr.toLowerCase().trim();
  if (abr == 'no') {
    let noabr = promptFn("Are you one of the following: Hindu, Taoist, Buddhist? (Type your answer or 'no'");

    if (noabr == 'no') {
      religion = 'Spiritual';
    } else if (noabr == 'hindu') {
      religion = 'Hindu';
    } else if (noabr == 'buddhist') {
      religion = 'Buddhist';
    } else if (noabr == 'taoist') {
      religion = 'Taoist';
    }
  } else if (abr == 'yes') {
    let yesabr = promptFn("Are you one of the following: Islamic, Christian, Jewish? (Type your anwer or 'no')");
    yesabr = yesabr.toLowerCase().trim();
    if (yesabr == 'no') {
      religion = 'Spiritual';
    } else if (yesabr == 'christian') {
      religion = 'Christian';
    } else if (yesabr == 'islamic') {
      religion = 'Islamic';
    } else if (yesabr == 'jewish') {
      religion = 'Jewish';
    }
  }
}

let gen = promptFn('What is your gender affiliation: Male, Female, Other?');
gender = '';
gen = gen.toLowerCase().trim();
if (gen == 'male') {
  gender = 'Male';
} else if (gen == 'female') {
  gender = 'Female';
} else if (gen == 'other') {
  gender = 'Other';
}

let pol = promptFn('Which political affiliation do you more closely align with: Conservative or Liberal?');
political = '';
pol = pol.toLowerCase().trim();
if (pol == 'conservative') {
  political = 'Traditional';
} else if (pol == 'liberal') {
  political = 'Liberal';
}

let your_choice = [religion, gender, political];

let value = -1;
for (let i = 0; i < categories.length; i++) {
  let match = 0;
  for (let j = 0; j < categories[0].length; j++) {
    console.log(categories[i][j] + '\t' + your_choice[j]);

    if (categories[i][j] === your_choice[j]) {
      match++;
    }
    if (match === 3) {
      value = i;
    }
  }
}
console.log(your_choice);
console.log('\n\nSELECTED OPTION WAS AT INDEX' + value);
