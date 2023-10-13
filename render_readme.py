SNIPPET_SOURCE_FILES = [
    'kustomize/tests/argocd/base/apps/app.yaml',
]


def parse_snippet(part):
    name, *snippet = part.split(' --')
    snippet = ' --'.join(snippet)
    snippet = snippet.split('# -- END SNIPPET --')[0].lstrip('\n').rstrip()
    return name, snippet


def load_snippets():
    snippets = {}
    for filename in SNIPPET_SOURCE_FILES:
        with open(filename, 'r') as f:
            for part in f.read().split('# -- START SNIPPET ')[1:]:
                name, snippet = parse_snippet(part)
                snippets[name] = snippet
    return snippets


def render_readme(snippets):
    with open('README.template.md', 'r') as f:
        readme = f.read()
    for name, snippet in snippets.items():
        readme = readme.replace(f'# -- SNIPPET {name} --', snippet)
    return readme


def main():
    snippets = load_snippets()
    readme = render_readme(snippets)
    print(readme)


if __name__ == '__main__':
    main()
