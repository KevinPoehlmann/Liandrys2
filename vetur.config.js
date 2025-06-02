/** @type {import('vls').VeturConfig} */
module.exports = {
  projects: [
    {
      root: './frontend/app',
      package: './package.json',
      tsconfig: './jsconfig.json', // use jsconfig.json since you're not using TS yet
    },
    {
      root: './frontend/admin',
      package: './package.json',
      tsconfig: './jsconfig.json',
    }
  ]
}
