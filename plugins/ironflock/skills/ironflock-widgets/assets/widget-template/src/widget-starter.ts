import { html, css, LitElement, PropertyValues } from 'lit'
import { customElement, property, state } from 'lit/decorators.js'
import { repeat } from 'lit/directives/repeat.js'
import { styleMap } from 'lit/directives/style-map.js'
import { StarterConfiguration } from './definition-schema.js'

type Theme = { theme_name: string; theme_object?: any }

/** One number on the tile: a data series, or one pivot value of a series. */
type Readout = {
    key: string
    label: string
    value?: number
    unit: string
    precision: number
    color?: string
}

/** A finite number, or undefined for null, '', NaN and anything else that is not numeric. */
const toNumber = (value: unknown): number | undefined => {
    if (value === null || value === undefined || value === '') return undefined
    const number = typeof value === 'number' ? value : Number(value)
    return Number.isFinite(number) ? number : undefined
}

const clampInt = (value: unknown, min: number, max: number): number => {
    const number = Math.round(Number(value))
    return Number.isFinite(number) ? Math.min(max, Math.max(min, number)) : min
}

// No locale given: numbers are formatted the way the viewer reads them.
const formatters = new Map<number, Intl.NumberFormat>()
const formatNumber = (value: number, precision: number): string => {
    let formatter = formatters.get(precision)
    if (!formatter) {
        formatter = new Intl.NumberFormat(undefined, {
            minimumFractionDigits: precision,
            maximumFractionDigits: precision
        })
        formatters.set(precision, formatter)
    }
    return formatter.format(value)
}

/**
 * What the tile shows, derived from the config. Pure: the config belongs to the
 * host, which may share its rows with other tiles, so nothing here writes to it.
 * Every field may be missing or have the wrong type (configs written for older
 * versions, hand-written board templates), so each one is checked, not trusted.
 */
function toReadouts(config?: StarterConfiguration): Readout[] {
    const series = Array.isArray(config?.dataseries) ? config.dataseries : []
    return series.flatMap((ds, index) => {
        if (!ds || typeof ds !== 'object') return [] // a null slot in a hand-written list
        // Rows arrive oldest first, so the last row of each pivot value is its newest.
        const newest = new Map<string, unknown>()
        for (const row of Array.isArray(ds.data) ? ds.data : []) {
            if (!row || typeof row !== 'object') continue
            newest.set(row.pivot === null || row.pivot === undefined ? '' : String(row.pivot), row.value)
        }
        // A series without rows keeps its label on the tile, with a dash for the value.
        if (newest.size === 0) newest.set('', undefined)
        return [...newest.entries()]
            .sort(([a], [b]) => a.localeCompare(b, undefined, { numeric: true }))
            .map(([pivot, value]) => ({
                key: `${index}:${pivot}`,
                label: [pivot, typeof ds.label === 'string' ? ds.label : ''].filter(Boolean).join(' - '),
                value: toNumber(value),
                unit: typeof ds.unit === 'string' ? ds.unit : '',
                precision: clampInt(ds.precision, 0, 6),
                // The editor stores an unset colour as '', so '' means "no colour" too.
                color: typeof ds.color === 'string' && ds.color ? ds.color : undefined
            }))
    })
}

@customElement('widget-starter-versionplaceholder')
export class WidgetStarter extends LitElement {
    /** This tile's config, with every data binding already replaced by its data. */
    @property({ type: Object }) inputData?: StarterConfiguration

    /** The board's ECharts theme. theme_object is missing on boards without a theme. */
    @property({ type: Object }) theme?: Theme

    @state() private readouts: Readout[] = []

    version: string = 'versionplaceholder'

    protected willUpdate(changed: PropertyValues<this>): void {
        // A new inputData object arrives with every data update. Derive what the
        // tile shows once per change, here, rather than on every render.
        if (changed.has('inputData')) this.readouts = toReadouts(this.inputData)
    }

    static styles = css`
        :host {
            display: block;
            box-sizing: border-box;
            overflow: hidden;
            font-family: sans-serif;
            /* The cq units below size everything by this tile. */
            container-type: size;
        }

        .paging:not([active]) {
            display: none !important;
        }

        .wrapper {
            display: flex;
            flex-direction: column;
            height: 100%;
            padding: 2cqh 2cqw;
            box-sizing: border-box;
        }

        h3,
        p {
            margin: 0;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        h3 {
            font-size: clamp(12px, 7cqh, 20px);
        }

        p {
            margin-top: 0.3em;
            font-size: clamp(10px, 5cqh, 14px);
        }

        .readouts {
            flex: 1;
            min-height: 0;
            display: grid;
            grid-template-columns: repeat(var(--columns, 1), minmax(0, 1fr));
            align-content: center;
            gap: 3cqmin;
        }

        .readout {
            min-width: 0;
            /* One size for every readout on the tile, so the numbers line up. */
            font-size: clamp(10px, min(calc(32cqh / var(--rows, 1)), calc(16cqw / var(--columns, 1))), 96px);
            line-height: 1.1;
        }

        .label {
            font-size: 0.5em;
            font-weight: 300;
            overflow: hidden;
            text-overflow: ellipsis;
            white-space: nowrap;
        }

        .value {
            font-weight: 600;
            white-space: nowrap;
        }

        .unit {
            font-size: 0.5em;
            font-weight: 300;
        }

        .no-data {
            flex: 1;
            display: flex;
            align-items: center;
            justify-content: center;
            font-size: clamp(12px, 8cqmin, 20px);
        }
    `

    render() {
        const title = this.inputData?.title
        const subTitle = this.inputData?.subTitle
        // The host's --re-text-color wins and the theme's colour is the fallback.
        // Nothing is resolved here, so a board style edit repaints without a new
        // render; and because this runs on every render, a theme_object that is
        // filled in after the theme was set is picked up too.
        const themeTitle = this.theme?.theme_object?.title
        const textColor = `var(--re-text-color, ${themeTitle?.textStyle?.color ?? 'inherit'})`
        const subtextColor = `var(--re-text-color, ${themeTitle?.subtextStyle?.color ?? themeTitle?.textStyle?.color ?? 'inherit'})`
        const columns = Math.max(1, Math.ceil(Math.sqrt(this.readouts.length)))
        const rows = Math.max(1, Math.ceil(this.readouts.length / columns))

        return html`
            <div class="wrapper" style=${styleMap({ color: textColor })}>
                <header class="paging" ?active=${!!title || !!subTitle}>
                    <h3 class="paging" ?active=${!!title}>${title}</h3>
                    <p class="paging" ?active=${!!subTitle} style=${styleMap({ color: subtextColor })}>
                        ${subTitle}
                    </p>
                </header>
                <div
                    class="readouts paging"
                    ?active=${this.readouts.length > 0}
                    style=${styleMap({ '--columns': String(columns), '--rows': String(rows) })}
                >
                    ${repeat(
                        this.readouts,
                        (readout) => readout.key,
                        (readout) => html`
                            <div class="readout">
                                <div class="label">${readout.label}</div>
                                <div class="value" style=${styleMap({ color: readout.color })}>
                                    ${readout.value === undefined
                                        ? '–'
                                        : formatNumber(readout.value, readout.precision)}
                                    <span class="unit">${readout.unit}</span>
                                </div>
                            </div>
                        `
                    )}
                </div>
                <div class="no-data paging" ?active=${this.readouts.length === 0}>No Data</div>
            </div>
        `
    }
}
