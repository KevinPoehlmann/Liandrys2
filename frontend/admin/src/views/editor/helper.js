export const getChanges = (objNew, objOld, k="") => {
    if(!(objNew && objOld)) {
        return []
    }
    const changedFields = []
    for(const [key, value] of Object.entries(objNew)) {
        if( typeof value === "object") {
        if(objOld[key]) {
            changedFields.push(...getChanges(value, objOld[key], `${k}${key} > `))
        } else {
            if( value != null) {
            changedFields.push(`${k}${key}: None -> ${value}`)
            }
        }
        } else {
        if(value != objOld[key]) {
            changedFields.push(`${k}${key}:   ${objOld[key]} -> ${value}`)
        }
        }
    }
    return changedFields
}



export const isEqual = (obj1, obj2) => {
    if (typeof obj1 === 'object' || typeof obj2 === 'object') {
      for (const key in obj1) {
        if (!isEqual(obj1[key], obj2[key])) {
          return false;
        }
      }
      for (const key in obj2) {
        if (!(key in obj1)) {
          return false;
        }
      }
      return true
    }
    if (obj1 != obj2) {
      return false;
    }
    return true;
}



export const deepCopy = (obj) => {
    if (typeof obj !== 'object' || obj === null) {
      return obj;
    }
    const result = Array.isArray(obj) ? [] : {};
    for (const key in obj) {
      if (Object.prototype.hasOwnProperty.call(obj, key)) {
        result[key] = deepCopy(obj[key]);
      }
    }
    return result;
  }


  export const updateValue = (obj, field, value) => {
    const keys = field.split('.');
    // Get a reference to the nested property
    let nestedProperty = obj;
    for (let i = 0; i < keys.length - 1; i++) {
      nestedProperty = nestedProperty[keys[i]];
    }
    nestedProperty[keys[keys.length - 1]] = value
  };