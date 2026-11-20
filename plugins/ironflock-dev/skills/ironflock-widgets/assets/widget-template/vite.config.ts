import { defineConfig } from 'vite'
import { readFileSync } from 'fs'
import replace from '@rollup/plugin-replace'

const pkg = JSON.parse(readFileSync('./package.json', 'utf-8'))

export default defineConfig({
    server: { open: '/demo/', port: 8000 },
    resolve: {
        // echarts imports tslib; without the ES build the dev server fails on `__extends`.
        alias: { tslib: 'tslib/tslib.es6.js' },
        conditions: ['browser']
    },
    // Some dependencies read process.env.NODE_ENV, which does not exist in a browser.
    define: { 'process.env.NODE_ENV': JSON.stringify('production') },
    // Every published version registers its own tag, widget-starter-<version>.
    plugins: [replace({ versionplaceholder: pkg.version, preventAssignment: true })],
    build: {
        lib: { entry: 'src/widget-starter.ts', formats: ['es'], fileName: 'widget-starter' },
        sourcemap: true,
        rollupOptions: {
            // Provided by the host page's import map, so every widget shares one copy.
            // Externalize only packages the import map provides; bundle everything else.
            external: [/^lit/, /^@lit/]
        }
    }
})
