/*BLOCKID 1:1231231231231231, Setup, Lines: 3 - 2 to 4 : 100%;*/
libname raw '/data/landing/raw';
libname mart "/data/warehouse/mart";
%let cutoff = 2026;
/*ENDBLOCKID 1:1231231231231231, Setup;*/

/*BLOCKID 2:4564564564564564, Macro, Lines: 6 - 6 to 11 : 100%;*/
%macro dedupe(src, dst);
proc sort data=&src. out=&dst. nodupkey;
    by id;
run;
%mend dedupe;
/*ENDBLOCKID 2:4564564564564564, Macro;*/
