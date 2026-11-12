****Normalized Pace at 4-hour mark
clear all
set mat 11000
use "/home/wu/stata/data/full_split_sample.dta"

* get a measure for how fast they ran the last 2.195 kilometers relative to the first 40 kilometers.

gen normalized_pace = ((chiptime - split_40k)/2.195)/(split_40k/40)

* There are a few super extreme outliers (probably chip time errors or something. Let's trim top and bottom 5%

qui sum normalized_pace, detail
drop if normalized_pace < r(p5) | normalized_pace > r(p95)

* Now we want to plot the normalized pace by the finishing time that you are on pace for when you cross the 40k split.

gen pacechiptime = split_40k*1.054875

gen round1_pacechiptime = round(pacechiptime + .25, .5)

bys round1_pacechiptime: egen round1_normavg = mean(normalized_pace)
bys round1_pacechiptime: egen round1_normsd = sd(normalized_pace)
bys round1_pacechiptime: egen round1_normcount = count(_N)
gen round1_normse = round1_normsd/sqrt(round1_normcount)

sort round1_pacechiptime
keep if round1_pacechiptime ~= round1_pacechiptime[_n-1]

gen lower_ci = round1_normavg - 1.96*round1_normse
gen upper_ci = round1_normavg + 1.96*round1_normse

twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=225 & round1_pacechiptime <= 255, color(gs10))  (connected round1_normavg round1_pacechiptime if round1_pacechiptime >= 225 & round1_pacechiptime <= 255, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (30-second increments)") ytitle("Normalized Pace For Last 2.195 kilometers") xlabel(225 "3:45" 230 "3:50" 235 "3:55" 240 "4:00" 245 "4:05" 250 "4:10" 255 "4:15")  xline(240, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 

graph save "/home/wu/stata/figures/norm_pace_4hr.gph", replace



****Normalized Pace Across entire range


twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=165 & round1_pacechiptime <= 315, color(gs10))  (connected round1_normavg round1_pacechiptime if round1_pacechiptime >= 165 & round1_pacechiptime <= 315, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (1-minute increments)") ytitle("Normalized Pace For Last 2.195 kilometers") xlabel(180 "3:00" 210 "3:30" 240 "4:00" 270 "4:30" 300 "5:00")  xline(180, lcolor(black) lpattern(shortdash)) xline(240, lcolor(black) lpattern(shortdash)) xline(300, lcolor(black) lpattern(shortdash))  xline(210, lcolor(black) lpattern(shortdash)) xline(270, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 


graph save "/home/wu/stata/figures/norm_pace_entire_range.gph", replace







***Let's do 2 panels - a close up at 4-hour mark and an full coverage graph for normalized pace, speed up, slow down.

**do the close up graph with 30 second bins and 60 second bins for the second graph






********Let's look at the probability of speeding up 

****Speeding up at 4-hour mark
clear all
set mat 11000
use "/home/wu/stata/data/full_split_sample.dta"


gen normalized_pace = ((chiptime - split_40k)/2.195)/(split_40k/40)

*There are a few super extreme outliers (probably chip time errors or something. Let's trim top and bottom 5%
qui sum normalized_pace, detail
drop if normalized_pace < r(p5) | normalized_pace > r(p95)


gen speedup = 0
replace speedup = 1 if normalized_pace < 1


*Now we want to plot the prob of speeding up by the finishing time that you are on pace for when you cross the 40k split.
gen pacechiptime = split_40k*1.054875

gen round1_pacechiptime = round(pacechiptime + .25, .5)

bys round1_pacechiptime: egen round1_speedupprob = mean(speedup)
bys round1_pacechiptime: egen round1_speedupsd = sd(speedup)
bys round1_pacechiptime: egen round1_speedupcount = count(_N)
gen round1_speedupse = round1_speedupsd/sqrt(round1_speedupcount)

sort round1_pacechiptime
keep if round1_pacechiptime ~= round1_pacechiptime[_n-1]

gen lower_ci = round1_speedupprob - 1.96*round1_speedupse
gen upper_ci = round1_speedupprob + 1.96*round1_speedupse

twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=225 & round1_pacechiptime <= 255, color(gs10))  (connected round1_speedupprob round1_pacechiptime if round1_pacechiptime >= 225 & round1_pacechiptime <= 255, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (30-second increments)") ytitle("Fraction Speeding Up In Last 2.195 kilometers") xlabel(225 "3:45" 230 "3:50" 235 "3:55" 240 "4:00" 245 "4:05" 250 "4:10" 255 "4:15")  xline(240, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 

graph save "/home/wu/stata/figures/speed_up_4hr.gph", replace

****Speeding up - entire range


twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=165 & round1_pacechiptime <= 315, color(gs10))  (connected round1_speedupprob round1_pacechiptime if round1_pacechiptime >= 165 & round1_pacechiptime <= 315, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (1-minute increments)") ytitle("Fraction Speeding Up In Last 2.195 kilometers") xlabel(180 "3:00" 210 "3:30" 240 "4:00" 270 "4:30" 300 "5:00")  xline(180, lcolor(black) lpattern(shortdash)) xline(240, lcolor(black) lpattern(shortdash)) xline(300, lcolor(black) lpattern(shortdash))  xline(210, lcolor(black) lpattern(shortdash)) xline(270, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 

graph save "/home/wu/stata/figures/speed_up_entire_range.gph", replace

















********Let's look at the probability of slowing down

****Slowing down at 4-hour mark
clear all
set mat 11000
use "/home/wu/stata/data/full_split_sample.dta"


gen normalized_pace = ((chiptime - split_40k)/2.195)/(split_40k/40)

*There are a few super extreme outliers (probably chip time errors or something. Let's trim top and bottom 5%
qui sum normalized_pace, detail
drop if normalized_pace < r(p5) | normalized_pace > r(p95)



gen slowdown = 0
replace slowdown = 1 if normalized_pace > 1.10

*Now we want to plot the prob of speeding up by the finishing time that you are on pace for when you cross the 40k split.
gen pacechiptime = split_40k*1.054875

gen round1_pacechiptime = round(pacechiptime + .25, .5)

bys round1_pacechiptime: egen round1_slowdownprob = mean(slowdown)
bys round1_pacechiptime: egen round1_slowdownsd = sd(slowdown)
bys round1_pacechiptime: egen round1_slowdowncount = count(_N)
gen round1_slowdownse = round1_slowdownsd/sqrt(round1_slowdowncount)

sort round1_pacechiptime
keep if round1_pacechiptime ~= round1_pacechiptime[_n-1]

gen lower_ci = round1_slowdownprob - 1.96*round1_slowdownse
gen upper_ci = round1_slowdownprob + 1.96*round1_slowdownse

twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=225 & round1_pacechiptime <= 255, color(gs10))  (connected round1_slowdownprob round1_pacechiptime if round1_pacechiptime >= 225 & round1_pacechiptime <= 255, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (30-second increments)") ytitle("Fraction Slowing Down In Last 2.195 kilometers") xlabel(225 "3:45" 230 "3:50" 235 "3:55" 240 "4:00" 245 "4:05" 250 "4:10" 255 "4:15")  xline(240, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 

graph save "/home/wu/stata/figures/slow_down_4hr.gph", replace




****Slowing down - entire range


twoway (rarea upper_ci lower_ci round1_pacechiptime if round1_pacechiptime >=165 & round1_pacechiptime <= 315, color(gs10))  (connected round1_slowdownprob round1_pacechiptime if round1_pacechiptime >= 165 & round1_pacechiptime <= 315, msize(vsmall) mcolor(black) lcolor(black)),  xtitle("40 kilometer Pace (1-minute increments)") ytitle("Fraction Slowing Down In Last 2.195 kilometers") xlabel(180 "3:00" 210 "3:30" 240 "4:00" 270 "4:30" 300 "5:00")  xline(180, lcolor(black) lpattern(shortdash)) xline(240, lcolor(black) lpattern(shortdash)) xline(300, lcolor(black) lpattern(shortdash))  xline(210, lcolor(black) lpattern(shortdash)) xline(270, lcolor(black) lpattern(shortdash)) graphregion(color(white)) ylabel(, nogrid) legend(off) 

graph save "/home/wu/stata/figures/slow_down_entire_range.gph", replace














