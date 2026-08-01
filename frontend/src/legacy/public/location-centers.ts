export interface LocationCenter {
  latitude: number;
  longitude: number;
}


interface RegionCenter extends LocationCenter {
  districts: Readonly<Record<string, LocationCenter>>;
}


// v1656 haqiqat manbai: static/regions.js.
const LOCATION_CENTERS: Readonly<Record<string, RegionCenter>> = {
  "Toshkent shahri": {
    latitude: 41.311,
    longitude: 69.28,
    districts: {
      "Bektemir": { latitude: 41.206, longitude: 69.333 },
      "Chilonzor": { latitude: 41.276, longitude: 69.204 },
      "Mirobod": { latitude: 41.292, longitude: 69.28 },
      "Mirzo Ulug'bek": { latitude: 41.336, longitude: 69.339 },
      "Olmazor": { latitude: 41.359, longitude: 69.229 },
      "Sergeli": { latitude: 41.226, longitude: 69.221 },
      "Uchtepa": { latitude: 41.287, longitude: 69.183 },
      "Shayxontohur": { latitude: 41.325, longitude: 69.239 },
      "Yakkasaroy": { latitude: 41.281, longitude: 69.252 },
      "Yashnobod": { latitude: 41.292, longitude: 69.321 },
      "Yunusobod": { latitude: 41.368, longitude: 69.289 },
    },
  },
  "Toshkent viloyati": {
    latitude: 41,
    longitude: 69.5,
    districts: {
      "Angren": { latitude: 41.017, longitude: 70.144 },
      "Bekobod": { latitude: 40.221, longitude: 69.27 },
      "Bo'ka": { latitude: 40.811, longitude: 69.203 },
      "Bo'stonliq (Gazalkent)": { latitude: 41.555, longitude: 69.778 },
      "Chinoz": { latitude: 40.937, longitude: 68.764 },
      "Chirchiq": { latitude: 41.469, longitude: 69.582 },
      "Nurafshon": { latitude: 41.038, longitude: 69.353 },
      "Ohangaron": { latitude: 40.908, longitude: 69.639 },
      "Oqqo'rg'on": { latitude: 40.875, longitude: 69.074 },
      "Parkent": { latitude: 41.293, longitude: 69.679 },
      "Piskent": { latitude: 40.892, longitude: 69.349 },
      "Qibray": { latitude: 41.392, longitude: 69.426 },
      "Yangiyo'l": { latitude: 41.113, longitude: 69.048 },
      "Zangiota": { latitude: 41.234, longitude: 69.139 },
    },
  },
  "Andijon viloyati": {
    latitude: 40.782,
    longitude: 72.344,
    districts: {
      "Andijon shahri": { latitude: 40.782, longitude: 72.344 },
      "Asaka": { latitude: 40.643, longitude: 72.238 },
      "Baliqchi": { latitude: 40.838, longitude: 71.963 },
      "Bo'z": { latitude: 40.638, longitude: 72.443 },
      "Buloqboshi": { latitude: 40.588, longitude: 72.512 },
      "Izboskan": { latitude: 40.918, longitude: 72.018 },
      "Jalaquduq": { latitude: 40.708, longitude: 72.512 },
      "Marhamat": { latitude: 40.467, longitude: 72.317 },
      "Oltinko'l": { latitude: 40.834, longitude: 72.23 },
      "Paxtaobod": { latitude: 40.918, longitude: 72.33 },
      "Qo'rg'ontepa": { latitude: 40.738, longitude: 72.73 },
      "Shahrixon": { latitude: 40.713, longitude: 72.058 },
      "Ulug'nor": { latitude: 40.847, longitude: 71.838 },
      "Xo'jaobod": { latitude: 40.658, longitude: 72.563 },
    },
  },
  "Farg'ona viloyati": {
    latitude: 40.386,
    longitude: 71.786,
    districts: {
      "Farg'ona shahri": { latitude: 40.386, longitude: 71.786 },
      "Marg'ilon": { latitude: 40.471, longitude: 71.724 },
      "Qo'qon": { latitude: 40.529, longitude: 70.943 },
      "Quvasoy": { latitude: 40.3, longitude: 71.976 },
      "Beshariq": { latitude: 40.428, longitude: 70.612 },
      "Bog'dod": { latitude: 40.428, longitude: 71.148 },
      "Buvayda": { latitude: 40.523, longitude: 71.039 },
      "Dang'ara": { latitude: 40.43, longitude: 71.345 },
      "Furqat": { latitude: 40.47, longitude: 71.45 },
      "Qo'shtepa": { latitude: 40.342, longitude: 71.654 },
      "Rishton": { latitude: 40.357, longitude: 71.277 },
      "So'x": { latitude: 39.943, longitude: 71.146 },
      "Toshloq": { latitude: 40.438, longitude: 71.849 },
      "Uchko'prik": { latitude: 40.524, longitude: 71.08 },
      "Yozyovon": { latitude: 40.629, longitude: 71.732 },
    },
  },
  "Namangan viloyati": {
    latitude: 40.998,
    longitude: 71.673,
    districts: {
      "Namangan shahri": { latitude: 40.998, longitude: 71.673 },
      "Chortoq": { latitude: 41.067, longitude: 71.819 },
      "Chust": { latitude: 41.001, longitude: 71.239 },
      "Kosonsoy": { latitude: 41.25, longitude: 71.546 },
      "Mingbuloq": { latitude: 40.846, longitude: 71.435 },
      "Norin": { latitude: 40.953, longitude: 71.73 },
      "Pop": { latitude: 40.873, longitude: 71.106 },
      "To'raqo'rg'on": { latitude: 41.06, longitude: 71.503 },
      "Uchqo'rg'on": { latitude: 41.113, longitude: 72.09 },
      "Uychi": { latitude: 41.073, longitude: 71.931 },
      "Yangiqo'rg'on": { latitude: 41.171, longitude: 71.728 },
    },
  },
  "Samarqand viloyati": {
    latitude: 39.654,
    longitude: 66.96,
    districts: {
      "Samarqand shahri": { latitude: 39.654, longitude: 66.96 },
      "Kattaqo'rg'on": { latitude: 39.899, longitude: 66.255 },
      "Bulung'ur": { latitude: 39.768, longitude: 67.27 },
      "Ishtixon": { latitude: 39.962, longitude: 66.473 },
      "Jomboy": { latitude: 39.713, longitude: 67.108 },
      "Qo'shrabot": { latitude: 40.218, longitude: 66.7 },
      "Narpay (Oqtosh)": { latitude: 39.917, longitude: 66.3 },
      "Nurobod": { latitude: 39.683, longitude: 66 },
      "Oqdaryo": { latitude: 39.842, longitude: 66.917 },
      "Pastdarg'om": { latitude: 39.567, longitude: 66.817 },
      "Paxtachi": { latitude: 39.917, longitude: 66.217 },
      "Payariq": { latitude: 39.933, longitude: 66.95 },
      "Toyloq": { latitude: 39.658, longitude: 67.033 },
      "Urgut": { latitude: 39.404, longitude: 67.241 },
    },
  },
  "Buxoro viloyati": {
    latitude: 39.775,
    longitude: 64.429,
    districts: {
      "Buxoro shahri": { latitude: 39.775, longitude: 64.429 },
      "Kogon": { latitude: 39.722, longitude: 64.553 },
      "G'ijduvon": { latitude: 40.103, longitude: 64.683 },
      "Jondor": { latitude: 39.745, longitude: 64.247 },
      "Qorako'l": { latitude: 39.497, longitude: 63.84 },
      "Qorovulbozor": { latitude: 39.503, longitude: 64.792 },
      "Olot": { latitude: 39.423, longitude: 63.927 },
      "Peshku": { latitude: 40.018, longitude: 64.317 },
      "Romitan": { latitude: 39.933, longitude: 64.383 },
      "Shofirkon": { latitude: 40.118, longitude: 64.51 },
      "Vobkent": { latitude: 40.018, longitude: 64.517 },
    },
  },
  "Qashqadaryo viloyati": {
    latitude: 38.861,
    longitude: 65.789,
    districts: {
      "Qarshi": { latitude: 38.861, longitude: 65.789 },
      "Shahrisabz": { latitude: 39.058, longitude: 66.831 },
      "Kitob": { latitude: 39.13, longitude: 66.879 },
      "G'uzor": { latitude: 38.621, longitude: 66.25 },
      "Qamashi": { latitude: 38.819, longitude: 66.451 },
      "Koson": { latitude: 39.04, longitude: 65.585 },
      "Mirishkor (Pomuq)": { latitude: 38.917, longitude: 65.4 },
      "Muborak": { latitude: 39.253, longitude: 65.15 },
      "Nishon": { latitude: 38.617, longitude: 65.617 },
      "Chiroqchi": { latitude: 39.034, longitude: 66.575 },
      "Yakkabog'": { latitude: 38.95, longitude: 66.683 },
      "Dehqonobod": { latitude: 38.35, longitude: 66.45 },
      "Kasbi": { latitude: 38.817, longitude: 65.633 },
    },
  },
  "Surxondaryo viloyati": {
    latitude: 37.224,
    longitude: 67.278,
    districts: {
      "Termiz": { latitude: 37.224, longitude: 67.278 },
      "Denov": { latitude: 38.276, longitude: 67.894 },
      "Boysun": { latitude: 38.207, longitude: 67.198 },
      "Sho'rchi": { latitude: 37.983, longitude: 67.789 },
      "Angor": { latitude: 37.467, longitude: 67.15 },
      "Jarqo'rg'on": { latitude: 37.502, longitude: 67.421 },
      "Qiziriq": { latitude: 37.567, longitude: 67.033 },
      "Qumqo'rg'on": { latitude: 37.834, longitude: 67.585 },
      "Muzrabot": { latitude: 37.617, longitude: 67.25 },
      "Oltinsoy": { latitude: 38.15, longitude: 67.917 },
      "Sariosiyo": { latitude: 38.417, longitude: 67.95 },
      "Sherobod": { latitude: 37.667, longitude: 66.967 },
      "Uzun": { latitude: 38.25, longitude: 68.017 },
    },
  },
  "Jizzax viloyati": {
    latitude: 40.116,
    longitude: 67.842,
    districts: {
      "Jizzax shahri": { latitude: 40.116, longitude: 67.842 },
      "Arnasoy": { latitude: 40.417, longitude: 68.417 },
      "Baxmal": { latitude: 39.817, longitude: 68.017 },
      "Do'stlik": { latitude: 40.517, longitude: 68.017 },
      "Forish": { latitude: 40.5, longitude: 67 },
      "G'allaorol": { latitude: 40.017, longitude: 67.6 },
      "Mirzacho'l": { latitude: 40.5, longitude: 68.2 },
      "Paxtakor": { latitude: 40.317, longitude: 67.95 },
      "Yangiobod": { latitude: 40.017, longitude: 68 },
      "Zomin": { latitude: 39.95, longitude: 68.4 },
      "Zarbdor": { latitude: 40.217, longitude: 68.2 },
      "Sharof Rashidov": { latitude: 40.116, longitude: 67.842 },
    },
  },
  "Sirdaryo viloyati": {
    latitude: 40.489,
    longitude: 68.784,
    districts: {
      "Guliston": { latitude: 40.489, longitude: 68.784 },
      "Yangiyer": { latitude: 40.267, longitude: 68.817 },
      "Shirin": { latitude: 40.233, longitude: 69 },
      "Boyovut": { latitude: 40.417, longitude: 68.9 },
      "Sayxunobod": { latitude: 40.517, longitude: 68.7 },
      "Sardoba": { latitude: 40.5, longitude: 68.6 },
      "Mirzaobod": { latitude: 40.6, longitude: 68.5 },
      "Oqoltin": { latitude: 40.5, longitude: 68.5 },
      "Xovos": { latitude: 40.217, longitude: 68.7 },
      "Sirdaryo": { latitude: 40.833, longitude: 68.661 },
    },
  },
  "Navoiy viloyati": {
    latitude: 40.084,
    longitude: 65.379,
    districts: {
      "Navoiy shahri": { latitude: 40.084, longitude: 65.379 },
      "Zarafshon": { latitude: 41.572, longitude: 64.205 },
      "Karmana": { latitude: 40.133, longitude: 65.35 },
      "Konimex": { latitude: 40.25, longitude: 65.15 },
      "Qiziltepa": { latitude: 40.05, longitude: 64.85 },
      "Navbahor": { latitude: 40.2, longitude: 65.5 },
      "Nurota": { latitude: 40.567, longitude: 65.683 },
      "Tomdi": { latitude: 41.733, longitude: 64.617 },
      "Uchquduq": { latitude: 42.158, longitude: 63.555 },
      "Xatirchi": { latitude: 40.217, longitude: 65.8 },
    },
  },
  "Xorazm viloyati": {
    latitude: 41.55,
    longitude: 60.631,
    districts: {
      "Urganch": { latitude: 41.55, longitude: 60.631 },
      "Xiva": { latitude: 41.378, longitude: 60.364 },
      "Bog'ot": { latitude: 41.433, longitude: 60.8 },
      "Gurlan": { latitude: 41.817, longitude: 60.383 },
      "Xonqa": { latitude: 41.467, longitude: 60.717 },
      "Hazorasp": { latitude: 41.317, longitude: 61.067 },
      "Qo'shko'pir": { latitude: 41.617, longitude: 60.45 },
      "Shovot": { latitude: 41.633, longitude: 60.35 },
      "Yangiariq": { latitude: 41.35, longitude: 60.55 },
      "Yangibozor": { latitude: 41.733, longitude: 60.5 },
    },
  },
  "Qoraqalpog'iston Respublikasi": {
    latitude: 42.46,
    longitude: 59.617,
    districts: {
      "Nukus": { latitude: 42.46, longitude: 59.617 },
      "Beruniy": { latitude: 41.683, longitude: 60.75 },
      "Chimboy": { latitude: 42.933, longitude: 59.783 },
      "Ellikqal'a (Bo'ston)": { latitude: 41.717, longitude: 60.517 },
      "Kegeyli": { latitude: 42.783, longitude: 59.617 },
      "Mo'ynoq": { latitude: 43.767, longitude: 59.02 },
      "Qonliko'l": { latitude: 43.133, longitude: 58.833 },
      "Qo'ng'irot": { latitude: 43.033, longitude: 58.9 },
      "Qorao'zak": { latitude: 42.917, longitude: 60.017 },
      "Shumanay": { latitude: 42.633, longitude: 58.917 },
      "Taxtako'pir": { latitude: 43.033, longitude: 60.317 },
      "To'rtko'l": { latitude: 41.55, longitude: 61 },
      "Xo'jayli": { latitude: 42.4, longitude: 59.45 },
      "Amudaryo (Mang'it)": { latitude: 42.117, longitude: 60.067 },
    },
  },
};


function normalizeLocationName(value: string) {
  return value
    .toLocaleLowerCase("uz")
    .replace(/[’‘ʻʼ`]/g, "'")
    .replace(/\s+/g, " ")
    .replace(/ tumani/g, "")
    .replace(/ viloyati/g, "")
    .trim();
}


function namesMatch(left: string, right: string) {
  const first = normalizeLocationName(left);
  const second = normalizeLocationName(right);
  return Boolean(
    first
    && second
    && (first.includes(second) || second.includes(first))
  );
}


export function findLocationCenter(
  regionName: string,
  districtName: string,
): LocationCenter | null {
  let fallback: LocationCenter | null = null;
  for (const [region, value] of Object.entries(LOCATION_CENTERS)) {
    if (!namesMatch(region, regionName)) continue;
    fallback = { latitude: value.latitude, longitude: value.longitude };
    for (const [district, center] of Object.entries(value.districts)) {
      if (namesMatch(district, districtName)) return center;
    }
    return fallback;
  }
  return fallback;
}
