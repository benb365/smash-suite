export default function (_modules, callHost) {
  return {
    call(name, data, callback) {
      Promise.resolve(callHost(name, data)).then(
        (value) => callback({ value }),
        (error) => callback({ error: String(error?.message ?? error) }),
      );
    },
  };
}
