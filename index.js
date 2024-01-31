const fs = require('fs');
const path = require('path');

const chokidar = require('chokidar');
const djot = require('@djot/djot')
const katex = require('katex')
const matter = require('gray-matter');
const mustache = require('mustache');
const liveServer = require('alive-server');


const ENCODING = 'utf8';
const DIR = {
    Styles: path.join(__dirname, 'less'),
    Output: path.join(__dirname, 'docs'),
    Pages: path.join(__dirname, 'pages'),
    Partials: path.join(__dirname, 'partials'),
    Templates: path.join(__dirname, 'templates'),
}

const relativeFromCWD = (to) => {
    return './' + path.relative(process.cwd(), to)
}

const renderPages = ({ inputDir, templatesDir, outputDir, partials, rebuild }, dir) => {
    if (!dir) dir = inputDir;
    for (let entery of fs.readdirSync(dir, ENCODING)) {
        let enteryPath = path.join(dir, entery);
        let enteryStats = fs.statSync(enteryPath);
        if (enteryStats.isDirectory()) {
            let outDir = path.join(
                outputDir,
                path.relative(inputDir, enteryPath)
            );
            if (!fs.existsSync(outDir)) {
                console.log(`mkdir: ${relativeFromCWD(outDir)}`)
                fs.mkdirSync(outDir);
            }
            renderPages({ inputDir, templatesDir, outputDir, partials, rebuild }, enteryPath);
            continue;
        }
        let outputFilePath = path.join(
            outputDir,
            path.relative(inputDir, dir),
            path.parse(entery).name + '.html'
        );
        if (!rebuild) {
            try {
                let outputFileStats = fs.statSync(outputFilePath);
                if (enteryStats.mtime <= outputFileStats.mtime) {
                    console.log(`render: ${relativeFromCWD(inputDir)}: skipping ./${path.relative(inputDir, enteryPath)}`)
                    continue;
                }
            } catch { }
        }
        let file = matter.read(enteryPath);
        let djotAST = djot.parse(file.content);
        let render = djot.renderHTML(djotAST, {
            overrides: {
                display_math: node => katex.renderToString(node.text, {
                    displayMode: true,
                    throwOnError: false,
                    trust: true,
                }),
                inline_math: node => katex.renderToString(node.text, {
                    displayMode: false,
                    throwOnError: false,
                    trust: true,
                }),
            }
        });
        if (file.data.template) {
            let { template, ...view } = file.data
            let templateFilePath = path.join(templatesDir, template);
            let templateContents = fs.readFileSync(templateFilePath, ENCODING);
            view['content'] = render
            render = mustache.render(templateContents, view, partials);
        }
        console.log(`render: ${relativeFromCWD(enteryPath)}`)
        fs.writeFileSync(outputFilePath, render, ENCODING);
    }
}

const render = ({ rebuild }) => {
    let partials = {};
    for (let file of fs.readdirSync(DIR.Partials, ENCODING)) {
        let filePath = path.join(DIR.Partials, file);
        partials[file] = fs.readFileSync(filePath, ENCODING);
    }
    console.log(`partials: ${relativeFromCWD(DIR.Partials)}: collected ${Object.keys(partials).length} partial(s)`)
    renderPages({ inputDir: DIR.Pages, templatesDir: DIR.Templates, outputDir: DIR.Output, partials, rebuild });
}

render({ rebuild: process.argv.includes("--rebuild") })
if (process.argv.includes('--watch'))
    chokidar.watch(Object.values(DIR)).on('change', () => render({ rebuild: false }));
if (process.argv.includes('--serve'))
    liveServer.start({
        root: DIR.Output,
        open: process.argv.includes('--open'),
        logLevel: 1,
    });
