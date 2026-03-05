import { defineConfig } from 'orval';

export default defineConfig({
  vectriva: {
    input: './openapi.json',
    output: {
      mode: 'tags-split',
      target: 'lib/api/generated',
      schemas: 'lib/api/generated/models',
      client: 'react-query',
      httpClient: 'axios',
      mock: false,
      override: {
        mutator: {
          path: './lib/axios-client.ts',
          name: 'customInstance',
        },
      },
    },
  },
});
