PYTHON=`which python`
DESTDIR=/
BUILDIR=$(CURDIR)/debian/aarddict
PROJECT=aarddict

all:
	@echo "make source - Create source package"
	@echo "make install - Install on local system"
	@echo "make deb - Generate a deb package"
	@echo "make clean - Get rid of scratch and byte files"

source:
	$(PYTHON) setup.py sdist $(COMPILE) --dist-dir=../
	rename -f 's/$(PROJECT)-(.*)\.tar\.gz/$(PROJECT)_$$1\.orig\.tar\.gz/' ../*
	dpkg-buildpackage -S -i -I -rfakeroot

install:
	$(PYTHON) setup.py install --root $(DESTDIR) $(COMPILE)

deb:
	 # build the source package in the parent directory
	 # then rename it to project_version.orig.tar.gz
	$(PYTHON) setup.py sdist $(COMPILE) --dist-dir=../
	rename -f 's/$(PROJECT)-(.*)\.tar\.gz/$(PROJECT)_$$1\.orig\.tar\.gz/' ../*
	 # build the package
	dpkg-buildpackage -i -I -rfakeroot

clean:
	$(PYTHON) setup.py clean
	fakeroot $(MAKE) -f $(CURDIR)/debian/rules clean
	rm -rf build/ MANIFEST
	find . -name '*.pyc' -delete