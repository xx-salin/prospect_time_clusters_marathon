capture prog drop bootstrap_excessmass
prog define bootstrap_excessmass

	* `1' is bunchpoint
	* `2' is bin size
	* `3' is bunching area
	* `4' is file name
	* `5' is number of reps
	
	clear all
*	set mat 11000
	
	use "`4'"
	
	*we round up so that running a 2:30 means you ran between 2:29:45 and 2:29:59

	quietly gen round1_chiptime = round(chiptime + .125, .25)
	
	quietly gen bunchpoint = `1'
	
	quietly keep if round1_chiptime <= (bunchpoint + `3') & round1_chiptime >= (bunchpoint - `3')
	
	quietly do "/home/wu/stata/do/see_boot2.do"
	
	quietly bootstrap r(outcome) r(actual) r(counter) r(excess), reps(`5'): se_boot2 `1' `2' `3' 
	
	
	display `1' ", "   %7.0f _b[_bs_2] ", " %7.0f  _b[_bs_3]  ", " %4.2f 100*((_b[_bs_2]/_b[_bs_3])-1)  "%, " %4.3f _b[_bs_4]/_se[_bs_4] ", "  %4.3f _b[_bs_1]/_se[_bs_1]
	
end
