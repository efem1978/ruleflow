import * as path from 'path';
import * as Mocha from 'mocha';
import * as fs from 'fs';

export function run(): Promise<void> {
  const mocha = new Mocha({ ui: 'bdd', color: true, timeout: 20000 });
  const testsRoot = path.resolve(__dirname);

  return new Promise((resolve, reject) => {
    fs.readdir(testsRoot, (err, files) => {
      if (err) {
        return reject(err);
      }

      files.filter(f => f.endsWith('.test.js')).forEach(f => mocha.addFile(path.resolve(testsRoot, f)));

      try {
        mocha.run((failures: number) => {
          if (failures > 0) {
            reject(new Error(`${failures} tests failed.`));
          } else {
            resolve();
          }
        });
      } catch (err) {
        reject(err);
      }
    });
  });
}
