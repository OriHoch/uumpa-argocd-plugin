import sys


def main(image):
    new_lines = []
    with open('manifests/patch-argocd-repo-server-deployment.yaml') as f:
        for line in f:
            if line.strip().startswith('image: '):
                pre, *_ = line.split(':')
                new_lines.append(f'{pre}: {image}\n')
            else:
                new_lines.append(line)
    with open('manifests/patch-argocd-repo-server-deployment.yaml', 'w') as f:
        f.writelines(new_lines)


if __name__ == '__main__':
    main(*sys.argv[1:])
