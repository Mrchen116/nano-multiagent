// Opt-in feasibility probe; published UI primitives include CSS imports.
export default {
  test: {
    include: ['packages/dsh-trajectory-viewer/probes/native-extension.probe.ts'],
    testTimeout: 15000,
    server: { deps: { inline: true } },
  },
};
