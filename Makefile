site:
	mkdir -p .site
	python3 build.py
	./tailwindcss-linux-x64 -i ./style.css -o .site/style.css --minify

page:
	python3 build.py $(word 2,$(MAKECMDGOALS))
%:
	@: # https://stackoverflow.com/a/6273809

clear:
	rm -rf .site/*

deploy:
	@echo "Are you sure you wish to deploy the current site to hkb.blog [enter]? "
	@read x
	git add .site -f
	git commit -m "deploy"
	git push origin `git subtree split --prefix .site master`:gh-pages --force
	git reset --soft HEAD~1
	git rm -r --cached .site
	