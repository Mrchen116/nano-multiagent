import { createLibrary } from '@openuidev/lang-core';
import { colorFunctions } from "./colors.js";
import { dataFunctions } from "./data.js";
import { dateFunctions } from "./dates.js";
import { listFunctions } from "./lists.js";
import { numberFunctions } from "./numbers.js";
import { textFunctions } from "./text.js";

/**
 * Generic functions the model calls as @Name(args) to compute inside a page:
 * edit lists held in $variables, do the math, format text and dates, and
 * shape Query rows for charts. They are pure except @Random, @Pick, @Shuffle
 * and @Now. Bad arguments, or a throw, make a call evaluate to null.
 */
export const functions = [...listFunctions, ...numberFunctions, ...textFunctions, ...colorFunctions, ...dateFunctions, ...dataFunctions];

const schemas = createLibrary({components: [], functions}).toJSONSchema().functions!;
/** Same pure function implementations as the browser, for canonical state snapshots. */
export const interactiveRuntimeFunctions = Object.fromEntries(functions.map(entry => [entry.name, {...schemas[entry.name], fn: entry.fn}]));
