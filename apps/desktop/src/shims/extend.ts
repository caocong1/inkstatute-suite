/**
 * ESM shim for the CJS 'extend' module.
 * Provides a deep-extend implementation compatible with the
 * `extend` npm package's API surface used by `unified`.
 */

function isPlainObject(obj: any): boolean {
  if (obj === null || obj === undefined) return false;
  return Object.prototype.toString.call(obj) === "[object Object]";
}

function deepExtend(target: any, source: any): any {
  if (source === undefined || source === null) return target;
  if (isPlainObject(source)) {
    if (!isPlainObject(target)) target = {};
    for (const key of Object.keys(source)) {
      const srcVal = (source as any)[key];
      const tgtVal = (target as any)[key];
      if (isPlainObject(srcVal) || Array.isArray(srcVal)) {
        (target as any)[key] = deepExtend(
          isPlainObject(tgtVal) ? tgtVal : (Array.isArray(srcVal) ? [] : {}),
          srcVal,
        );
      } else {
        (target as any)[key] = srcVal;
      }
    }
  } else if (Array.isArray(source)) {
    if (!Array.isArray(target)) target = [];
    for (let i = 0; i < source.length; i++) {
      const srcVal = source[i];
      if (isPlainObject(srcVal) || Array.isArray(srcVal)) {
        (target as any[])[i] = deepExtend(
          isPlainObject((target as any[])[i]) ? (target as any[])[i] : (Array.isArray(srcVal) ? [] : {}),
          srcVal,
        );
      } else {
        (target as any[])[i] = srcVal;
      }
    }
  }
  return target;
}

function shallowExtend(target: any, source: any): any {
  if (source === undefined || source === null) return target;
  for (const key of Object.keys(source)) {
    (target as any)[key] = (source as any)[key];
  }
  return target;
}

function extend(...args: any[]): any {
  let deep = false;
  let argIndex = 0;

  if (typeof args[0] === "boolean") {
    deep = args[0];
    argIndex = 1;
  }

  let target = args[argIndex];
  if (typeof target !== "object" && typeof target !== "function") {
    target = {};
  }
  if (target === null) {
    target = {};
  }
  argIndex++;

  for (let i = argIndex; i < args.length; i++) {
    const source = args[i];
    if (source === undefined || source === null) continue;
    if (deep) {
      target = deepExtend(target, source);
    } else {
      target = shallowExtend(target, source);
    }
  }

  return target;
}

export default extend;
